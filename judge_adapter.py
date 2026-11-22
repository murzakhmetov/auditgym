"""judge_adapter.py: the thin adapter of the Genesis FinTech check definitions (https://genesis-exe.com/fintech-checks.html).

    generate_episode(seed, config, output_dir)       -> None   writes one episode into output_dir
    make_env()                                       -> env    reset(seed, config), step(action)
    score_episode(episode_dir, findings, inspection_steps) -> dict

Standard library only; everything is a wrapper over `auditgym` (generator, `AuditEnv`, `Grader`). Run from the repository root
(`python -c "import judge_adapter"`); the Docker image has it at /app/judge_adapter.py with /app as the working directory.

Episode directory layout written by generate_episode (flat, the names of the case section 03):
    manifest.json  ledger.csv  invoices.jsonl  payments.jsonl  fx.csv  policy.json   (open records)
    truth.json     provenance.json                                                   (closed grader files)
A directory with the repository's own layout (public/ and grader/ subfolders, as in episodes/) is accepted everywhere too.

Action envelope: {"name": "list_records|get_record|get_document|calculator|submit", "args": {...}} (the repository's native
{"action": ..., ...} form is accepted as well). Results: list_records -> {"records": [...], "next_cursor": null_or_str};
get_record / get_document -> the record or document object; calculator -> a decimal string; submit -> {"accepted": true}.
Table names: ledger, invoices, payments, fx.

reset config: {"mode": "closed", "episode_dir": "...", "team_config": {...}} loads exactly that episode (closed: the policy-facing
reward is the number 0 on every step, info holds only episode_id); {"mode": "train", ...} without episode_dir generates from
seed and team_config, and returns the terminal reward on the last step. The tolerance of the amount match is the per-issue
`tolerance_minor` key of truth.json (absent means 0).
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import time
from pathlib import Path

from auditgym import schemas
from auditgym.env import AuditEnv
from auditgym.episode import Episode, load_episode
from auditgym.generator import generate_episode as _generate
from auditgym.grader import Grader

OPEN_FILES = ("manifest.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "policy.json")
CLOSED_FILES = ("truth.json", "provenance.json")
MODES = ("train", "closed")


# --------------------------------------------------------------------------------------------- episodes
def _read_truth(path: Path, manifest: dict) -> dict:
    """The closed answer key, read leniently: the fields of the case section 03 are enough (issue_id, type, affected_ids,
    expected_amount_minor, currency and the acceptable evidence sets under `evidence_sets` or `acceptable_evidence_sets`);
    `tolerance_minor` per issue (0 when absent) and `id_aliases` are optional, and extra keys are ignored."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or not isinstance(raw.get("issues", []), list):
        raise ValueError("truth.json must be an object with a list of issues")
    issues = []
    for n, issue in enumerate(raw.get("issues", []), 1):
        sets = issue.get("evidence_sets", issue.get("acceptable_evidence_sets"))
        if sets is None:
            raise ValueError(f"issue {n} of truth.json has no evidence_sets")
        entry = {"issue_id": issue.get("issue_id", f"iss_{n:02d}"), "type": issue["type"],
                 "affected_ids": list(issue["affected_ids"]), "expected_amount_minor": int(issue["expected_amount_minor"]),
                 "currency": issue["currency"], "evidence_sets": [list(s) for s in sets]}
        if "tolerance_minor" in issue:
            entry["tolerance_minor"] = int(issue["tolerance_minor"])
        issues.append(entry)
    return {"episode_id": raw.get("episode_id", manifest.get("episode_id")), "issues": issues,
            "id_aliases": dict(raw.get("id_aliases", {}))}


def _load(episode_dir, with_grader: bool = True) -> Episode:
    """Load an episode directory in the flat layout or in the repository's public/ + grader/ layout."""
    root = Path(episode_dir)
    if (root / "public" / "manifest.json").is_file():
        pub, closed = root / "public", root / "grader"
    elif (root / "manifest.json").is_file():
        pub, closed = root, root
    else:
        raise FileNotFoundError("no manifest.json in the episode directory")
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp)
        (staged / "public").mkdir()
        for name in OPEN_FILES:
            shutil.copyfile(pub / name, staged / "public" / name)
        episode = load_episode(staged, with_grader=False)
    if with_grader and (closed / "truth.json").is_file():
        episode.truth = _read_truth(closed / "truth.json", episode.manifest)
        if (closed / "provenance.json").is_file():
            episode.provenance = json.loads((closed / "provenance.json").read_text(encoding="utf-8-sig"))
    return episode


def generate_episode(seed: int, config: dict, output_dir: str) -> None:
    """Generate one episode with the team's generator and write it, flat, into output_dir."""
    gen = _generate(seed, dict(config or {}))
    out = Path(output_dir)
    with tempfile.TemporaryDirectory() as tmp:
        gen.episode.write(Path(tmp) / "ep")
        out.mkdir(parents=True, exist_ok=True)
        for name in OPEN_FILES:
            shutil.copyfile(Path(tmp) / "ep" / "public" / name, out / name)
        for name in CLOSED_FILES:
            shutil.copyfile(Path(tmp) / "ep" / "grader" / name, out / name)


# --------------------------------------------------------------------------------------------- environment
class JudgeEnv:
    """reset(seed, config) -> (observation, info); step(action) -> (observation, reward, terminated, truncated, info)."""

    def __init__(self, time_limit_s: float = 60.0, clock=time.monotonic):
        self._env: AuditEnv | None = None
        self._time_limit_s = time_limit_s
        self._clock = clock

    def reset(self, seed=None, config=None):
        config = dict(config or {})
        mode = config.get("mode", "train")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self._env = AuditEnv(mode="eval" if mode == "closed" else "train", allow_weak_seed=True,
                             time_limit_s=self._time_limit_s, clock=self._clock)
        team = config.get("team_config")
        team = dict(team) if isinstance(team, dict) else {}
        if config.get("episode_dir"):
            episode = _load(config["episode_dir"])
            native = {"episode": episode}
        else:
            native = dict(team)
        obs, info = self._env.reset(seed=seed, config=native)
        return obs, self._info(info)

    def step(self, action):
        if self._env is None:
            raise RuntimeError("call reset() first")
        obs, reward, terminated, truncated, info = self._env.step(self._native(action))
        return self._observation(obs), reward, terminated, truncated, self._info(info)

    # ------------------------------------------------------------------ translation
    @staticmethod
    def _native(action):
        """{"name": n, "args": {...}} -> the repository's {"action": n, ...}; anything else is passed through unchanged."""
        if isinstance(action, dict) and "name" in action and "action" not in action and set(action) <= {"name", "args"}:
            args = action.get("args")
            if args is None:
                args = {}
            if not isinstance(args, dict):
                return {"action": action["name"], "args": args}  # a bounded bad_args error comes back from the environment
            return {"action": action["name"], **copy.deepcopy(args)}
        return action

    @staticmethod
    def _observation(obs):
        """Reshape the result of a step observation to the shapes of the check definitions."""
        if "result" not in obs:
            return obs
        result = obs["result"]
        if isinstance(result, dict):
            if "rows" in result and "next_cursor" in result:
                result = {"records": result["rows"], "next_cursor": result["next_cursor"]}
            elif "record" in result and "table" in result:
                result = result["record"]
            elif "document" in result and "document_type" in result:
                result = result["document"]
            elif set(result) == {"value"}:
                result = result["value"]
            elif "accepted" in result:
                result = {"accepted": True}
        return {"result": result, "error": obs["error"], "remaining_steps": obs["remaining_steps"]}

    @staticmethod
    def _info(info):
        return {k: v for k, v in info.items() if k in ("episode_id", "final")}


def make_env() -> JudgeEnv:
    return JudgeEnv()


# --------------------------------------------------------------------------------------------- scoring
def score_episode(episode_dir: str, findings: dict, inspection_steps: int) -> dict:
    """Closed scoring of one submit. A valid submit returns tp, fp, fn, precision, recall, f1 and return (the terminal reward);
    an invalid one returns return = -1 with every other field null (the reason is in the grader's own report)."""
    episode = _load(episode_dir)
    submission = schemas.coerce_submission(copy.deepcopy(findings))
    errors = schemas.validate_submission(submission, episode.episode_id)
    grader = Grader(episode.truth, episode.episode_id, episode.known_ids())
    if errors:
        grader.grade(None, int(inspection_steps), "invalid_submission", invalid_errors=errors)
        return {"tp": None, "fp": None, "fn": None, "precision": None, "recall": None, "f1": None, "return": -1}
    report = grader.grade(submission, int(inspection_steps), "submitted")
    return {"tp": report["tp"], "fp": report["fp"], "fn": report["fn"], "precision": report["precision"],
            "recall": report["recall"], "f1": report["f1"], "return": report["reward"]}


__all__ = ["generate_episode", "make_env", "score_episode", "JudgeEnv"]

if __name__ == "__main__":  # a one-screen self-check: generate, reset in closed mode, explore, submit an empty answer
    import sys

    with tempfile.TemporaryDirectory() as tmp:
        generate_episode(7, {"size": "small"}, tmp)
        env = make_env()
        obs, info = env.reset(0, {"mode": "closed", "episode_dir": tmp, "team_config": {}})
        obs, reward, terminated, truncated, info = env.step({"name": "list_records", "args": {"table": "ledger", "cursor": None, "limit": 50}})
        print(json.dumps({"records": len(obs["result"]["records"]), "remaining_steps": obs["remaining_steps"]}))
        eid = info["episode_id"]
        obs, reward, terminated, truncated, info = env.step({"name": "submit", "args": {"findings": {"episode_id": eid, "findings": []}}})
        print(json.dumps({"result": obs["result"], "reward": reward, "terminated": terminated, "info": info}))
        print(json.dumps(score_episode(tmp, {"episode_id": eid, "findings": []}, 1)))
    sys.exit(0)
