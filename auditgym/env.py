"""AuditEnv: Gymnasium-style reset/step over a narrow, read-only tool interface.

    obs, info = env.reset(seed, config)
    obs, reward, terminated, truncated, info = env.step(action)

Observations hold only what the case allows: the requested records or tool
result, or a bounded error, plus the remaining budget. The reset observation
holds the task, manifest, full policy and the budget.

Grading happens inside the environment's process. In "eval" mode the reward
returned to the policy is always 0.0 and no diagnostics leave the grader until
the run ends; in "train" mode the terminal reward (and TP/FP/FN counts) are
returned on the final step only. Exploration steps always return 0.0.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path

from . import calculator, schemas
from .episode import Episode, load_episode
from .grader import Grader
from .task import build_task

MODES = ("train", "eval")
DEFAULT_MAX_STEPS = 100
DEFAULT_TIME_LIMIT_S = 60.0
ECHO_CHARS = 64
RESET_KEYS = {"episode_dir", "episode", "generator", "transform"}


def _echo(value) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = repr(value)
        except Exception:  # RecursionError on deeply nested input, or a failing __repr__
            text = f"<{type(value).__name__}>"
    return text if len(text) <= ECHO_CHARS else text[:ECHO_CHARS] + "..."


def _err(code: str, message: str) -> dict:
    return {"code": code, "message": message[:200]}


class AuditEnv:
    def __init__(self, mode: str = "train", max_steps: int = DEFAULT_MAX_STEPS,
                 time_limit_s: float = DEFAULT_TIME_LIMIT_S, clock=time.monotonic, secret: str | None = None):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if not 1 <= int(max_steps) <= DEFAULT_MAX_STEPS:
            raise ValueError("max_steps must be in [1, 100]")
        self.mode = mode
        self.max_steps = int(max_steps)
        self.time_limit_s = float(time_limit_s)
        self._clock = clock
        self._secret = secret
        self._episode: Episode | None = None
        self._grader: Grader | None = None
        self._index: dict = {}
        self._docs: dict = {}
        self._steps = 0
        self._done = False
        self._terminated = False
        self._truncated = False
        self._t0 = 0.0
        self._final = None

    # ------------------------------------------------------------------ reset
    def reset(self, seed=None, config=None, options=None):
        """Start a new episode; all previous episode state is discarded.

        config forms:
          {"generator": {...generator config...}}  (needs seed)  -- or the generator config itself
          {"episode_dir": "path/to/episode"}       load a pre-generated or transformed episode
          optional "transform": {"permute_seed": int, "remap_seed": int, "ts_repr": "local|utc|mixed"}
        options: reset(options={"config": ...}) is the same as config=... when no config is given;
        every other option key is ignored (never an error).
        """
        if config is None and isinstance(options, dict) and isinstance(options.get("config"), dict):
            config = options["config"]  # Gymnasium-style reset(options=...); any other option key is ignored
        config = dict(config or {})
        if "episode_dir" in config:
            episode = load_episode(Path(config["episode_dir"]))
        elif isinstance(config.get("episode"), Episode):
            episode = config["episode"]
        else:
            if seed is None:
                raise ValueError("seed is required to generate an episode")
            from .generator import generate_episode

            gen_cfg = config.get("generator", {k: v for k, v in config.items() if k not in RESET_KEYS})
            episode = generate_episode(seed, gen_cfg, secret=self._secret).episode
        if config.get("transform"):
            from .transform import transform_episode

            episode = transform_episode(episode, **config["transform"])
        self._load(episode)
        obs = {
            "task": build_task(episode, self.max_steps, self.mode),
            "manifest": copy.deepcopy(episode.manifest),
            "policy": copy.deepcopy(episode.policy),
            "remaining_steps": self.max_steps,
        }
        info = {"episode_id": episode.episode_id, "mode": self.mode, "max_steps": self.max_steps}
        return obs, info

    def _load(self, episode: Episode) -> None:
        self._episode = episode
        self._grader = Grader(episode.truth, episode.episode_id)
        self._index = {t: {Episode.record_key(t, r): r for r in episode.table(t)} for t in schemas.TABLES}
        self._docs = {r["doc_id"]: r for t in ("invoices", "payments") for r in episode.table(t)}
        self._steps = 0
        self._done = False
        self._terminated = False
        self._truncated = False
        self._final = None
        self._t0 = self._clock()

    # ------------------------------------------------------------------- step
    def step(self, action):
        if self._episode is None:
            raise RuntimeError("call reset() first")
        if self._done:
            obs = self._obs(None, _err("episode_finished", "The episode has ended; nothing was changed."))
            return obs, 0.0, self._terminated, self._truncated, self._info()
        if self._clock() - self._t0 > self.time_limit_s:
            self._finish(submission=None, truncated=True, reason="time_limit")
            obs = self._obs(None, _err("time_limit", "Time limit reached; an empty answer was recorded."))
            return obs, self._reward_out(), self._terminated, self._truncated, self._info()

        self._steps += 1
        if isinstance(action, dict) and set(action) == {"action", "args"} and isinstance(action["args"], dict) \
                and "action" not in action["args"]:
            action = {"action": action["action"], **action["args"]}  # accepted alias: {"action", "args": {...}}
        name = action.get("action") if isinstance(action, dict) else None
        if name == "submit":
            findings = schemas.coerce_submission(action.get("findings"))
            errors = schemas.validate_submission(findings, self._episode.episode_id)
            extra = sorted(map(schemas.safe_str, set(action) - {"action", "findings"}))
            if extra:
                errors.append("unknown action keys: " + _echo(", ".join(extra)))
            if errors:
                self._finish(submission=None, truncated=False, reason="invalid_submission", invalid=errors)
                obs = self._obs(None, _err("invalid_submission", "Submission rejected: invalid structure."))
            else:
                self._finish(submission=copy.deepcopy(findings), truncated=False, reason="submitted")
                obs = self._obs({"accepted": True, "findings_received": len(findings["findings"])}, None)
            return obs, self._reward_out(), self._terminated, self._truncated, self._info()

        try:
            result, error = self._dispatch(name, action)
        except Exception:  # never leak a traceback, path, or internal state
            result, error = None, _err("internal_error", "The action could not be processed.")
        if self._steps >= self.max_steps:
            self._finish(submission=None, truncated=True, reason="step_limit")
        obs = self._obs(result, error)
        return obs, self._reward_out(), self._terminated, self._truncated, self._info()

    # ---------------------------------------------------------------- tools
    def _dispatch(self, name, action):
        if not isinstance(action, dict):
            return None, _err("bad_args", "Action must be a JSON object.")
        if name not in schemas.ACTIONS:
            return None, _err("unknown_action", f"Unknown action {_echo(name)}.")
        allowed = {
            "list_records": {"action", "table", "cursor", "limit"},
            "get_record": {"action", "table", "id"},
            "get_document": {"action", "doc_id"},
            "calculator": {"action", "expression"},
        }[name]
        extra = sorted(map(schemas.safe_str, set(action) - allowed))
        if extra:
            return None, _err("bad_args", "Unknown argument(s): " + _echo(", ".join(extra)))
        return {
            "list_records": self._list_records,
            "get_record": self._get_record,
            "get_document": self._get_document,
            "calculator": self._calculator,
        }[name](action)

    def _table_arg(self, action):
        table = action.get("table")
        if not isinstance(table, str) or table not in schemas.TABLES:
            return None, _err("unknown_table", f"Unknown table {_echo(table)}; use one of {', '.join(schemas.TABLES)}.")
        return table, None

    def _list_records(self, action):
        table, err = self._table_arg(action)
        if err:
            return None, err
        limit = schemas.coerce_int(action.get("limit", schemas.MAX_PAGE))
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= schemas.MAX_PAGE:
            return None, _err("bad_args", f"limit must be an integer in [1, {schemas.MAX_PAGE}].")
        cursor = action.get("cursor")
        if cursor is not None and not isinstance(cursor, str):
            return None, _err("bad_args", "cursor must be a string or null.")
        rows = self._episode.table(table)
        if cursor is None:
            offset = 0
        elif isinstance(cursor, str) and cursor.isascii() and cursor.isdigit() and len(cursor) <= 6 and int(cursor) <= len(rows):
            offset = int(cursor)
        else:
            return None, _err("bad_cursor", f"Invalid cursor {_echo(cursor)}.")
        page = rows[offset: offset + limit]
        nxt = offset + len(page)
        return {
            "table": table,
            "rows": copy.deepcopy(page),
            "next_cursor": str(nxt) if nxt < len(rows) else None,
            "total": len(rows),
        }, None

    def _get_record(self, action):
        table, err = self._table_arg(action)
        if err:
            return None, err
        rid = action.get("id")
        if not isinstance(rid, str):
            return None, _err("bad_args", "id must be a string.")
        record = self._index[table].get(rid)
        if record is None:
            return None, _err("unknown_id", f"No record {_echo(rid)} in table {table}.")
        return {"table": table, "record": copy.deepcopy(record)}, None

    def _get_document(self, action):
        doc_id = action.get("doc_id")
        if not isinstance(doc_id, str):
            return None, _err("bad_args", "doc_id must be a string.")
        doc = self._docs.get(doc_id)
        if doc is None:
            return None, _err("unknown_id", f"No document {_echo(doc_id)}.")
        kind = "invoice" if "invoice_id" in doc else "payment"
        return {"document_type": kind, "document": copy.deepcopy(doc)}, None

    def _calculator(self, action):
        expr = action.get("expression")
        if not isinstance(expr, str):
            return None, _err("bad_args", "expression must be a string.")
        if len(expr) > schemas.MAX_EXPRESSION_CHARS:
            return None, _err("bad_args", f"expression is longer than {schemas.MAX_EXPRESSION_CHARS} characters.")
        try:
            value = calculator.evaluate(expr)
        except calculator.CalcError as exc:
            return None, _err("calc_error", str(exc)[:120])
        return {"value": value}, None

    # ------------------------------------------------------------- finishing
    def _finish(self, submission, truncated: bool, reason: str, invalid=None) -> None:
        self._done = True
        self._truncated = truncated
        self._terminated = not truncated
        inspection = self._steps - (1 if reason in ("submitted", "invalid_submission") else 0)
        self._final = self._grader.grade(
            submission=submission,
            inspection_steps=inspection,
            status=reason,
            invalid_errors=invalid,
            elapsed_s=self._clock() - self._t0,
        )

    def _reward_out(self) -> float:
        if not self._done or self.mode != "train":
            return 0.0
        return self._final["reward"]

    def _info(self) -> dict:
        info = {"episode_id": self._episode.episode_id}
        if self._done and self.mode == "train":
            f = self._final
            info["final"] = {k: f[k] for k in ("reward", "tp", "fp", "fn", "precision", "recall", "f1", "status")}
        return info

    def _obs(self, result, error) -> dict:
        return {"result": result, "error": error, "remaining_steps": max(0, self.max_steps - self._steps)}

    def elapsed_s(self) -> float:
        return self._clock() - self._t0

    def force_timeout(self) -> None:
        """Host-side: the agent did not answer in time; record an empty answer."""
        self.force_stop("time_limit")

    def force_stop(self, reason: str) -> None:
        """Host-side: end the episode with an empty answer (time limit, or the agent process exited)."""
        if self._episode is not None and not self._done:
            self._finish(submission=None, truncated=True, reason=reason)

    # ------------------------------------------------------- grader access
    @property
    def steps(self) -> int:
        return self._steps

    @property
    def done(self) -> bool:
        return self._done

    def grader_report(self) -> dict | None:
        """Grader-side only. Never send this to the agent during a closed run."""
        return copy.deepcopy(self._final)

    @property
    def episode(self) -> Episode | None:
        return self._episode
