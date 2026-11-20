"""In-process contract checks of the environment, used by `check` (section F_contract).

contract_battery(ep) runs one episode through AuditEnv without a child process and
returns [(label, ok, detail)], one named check per published rule: observation
shape, page size and cursor, bounded errors, calculator, termination, step and
time limits, eval-mode secrecy, scoring of bad submissions, the observation
JSON Schema, and a short seeded fuzz run. Offline and deterministic.
"""

from __future__ import annotations

import json

from . import schema_files, schemas
from .env import AuditEnv
from .policies.oracle import OraclePolicy
from .rng import Rng

FUZZ_ACTIONS = 300
FUZZ_SEED = "auditgym-contract-battery-v1"
RESET_KEYS = {"task", "manifest", "policy", "remaining_steps"}
STEP_KEYS = {"result", "error", "remaining_steps"}
INFO_KEYS = {"episode_id"}


def _env(ep, mode="eval", **kw) -> tuple:
    env = AuditEnv(mode=mode, clock=kw.pop("clock", lambda: 0.0), **kw)
    obs, info = env.reset(config={"episode": ep})
    return env, obs, info


def _submission(ep, findings) -> dict:
    return {"action": "submit", "findings": {"episode_id": ep.episode_id, "findings": findings}}


def _observations(ep) -> list:
    """The reset observation plus the observation of one call of every action and error kind."""
    env, obs, _ = _env(ep)
    out = [obs]
    table = schemas.TABLES[0]
    key = ep.record_key(table, ep.table(table)[0])
    for action in ({"action": "list_records", "table": table}, {"action": "get_record", "table": table, "id": key},
                   {"action": "get_document", "doc_id": ep.invoices[0]["doc_id"]},
                   {"action": "calculator", "expression": "1+2"}, {"action": "get_record", "table": table, "id": "nope"},
                   {"action": "nope"}, {"action": "calculator", "expression": "1/0"}, _submission(ep, []),
                   {"action": "list_records", "table": table}):
        out.append(env.step(action)[0])
    return out


def _fuzz_submit(rng: Rng, ctx: dict) -> dict:
    """An empty valid submission, or one broken in a way the environment must reject."""
    ep_id = ctx["episode_id"]
    return rng.choice(({"action": "submit", "findings": {"episode_id": ep_id, "findings": []}},
                       {"action": "submit", "findings": {"episode_id": "ep_foreign", "findings": []}},
                       {"action": "submit", "findings": {"episode_id": ep_id, "findings": [{"type": "nonsense"}]}},
                       {"action": "submit", "findings": None}, {"action": "submit"},
                       {"action": "submit", "findings": {"episode_id": ep_id, "findings": []}, "extra": 1}))


def _fuzz_action(rng: Rng, ctx: dict):
    """A valid call, a call with one thing broken, or a value that is not an action at all."""
    if rng.randbelow(40) == 0:
        return _fuzz_submit(rng, ctx)
    table = rng.choice(schemas.TABLES)
    valid = [{"action": "list_records", "table": table, "limit": rng.randint(1, 50)},
             {"action": "get_record", "table": table, "id": rng.choice(ctx["ids"][table])},
             {"action": "get_document", "doc_id": rng.choice(ctx["docs"])},
             {"action": "calculator", "expression": rng.choice(("1+2", "(1+2)*3/4", "7-9", "1/0", "2**8", ""))}]
    a = dict(rng.choice(valid))
    roll = rng.randbelow(8)
    if roll == 0:
        a[rng.choice(sorted(a))] = rng.choice((None, 7, [], {}, True, "x" * 500, " ", 1.5, -1))
    elif roll == 1 and len(a) > 1:
        del a[rng.choice(sorted(a))]
    elif roll == 2:
        a["extra"] = 1
    elif roll == 3:
        a["action"] = rng.choice(("LIST_RECORDS", "", "reset", "step", None, 3))
    elif roll == 4:
        a = {"action": "list_records", "table": table, "cursor": rng.choice(("999999", "-1", "abc", "", 5, "٣", "9" * 50))}
    elif roll == 5:
        return rng.choice((None, [], "list_records", 7, True, [a], 1.5))
    elif roll == 6:
        a = {"action": a["action"], "args": {k: v for k, v in a.items() if k != "action"}}
    return a


def _fuzz_problem(i, obs, reward, info, prev, state):
    """The first invariant the observation breaks, or None. state is (mode, episode already ended)."""
    mode, ended = state
    err = obs.get("error")
    if set(obs) != STEP_KEYS:
        return f"#{i}: keys {sorted(obs)}"
    if obs["remaining_steps"] != (prev if ended else max(0, prev - 1)):
        return f"#{i}: remaining_steps {prev} -> {obs['remaining_steps']}"
    if ended and (err or {}).get("code") != "episode_finished":
        return f"#{i}: step after the end answered {err}"
    if err and (err["code"] == "internal_error" or len(err["message"]) > 200 or obs["result"] is not None):
        return f"#{i}: bad error {err['code']}"
    if (obs["result"] is None) == (err is None):
        return f"#{i}: result and error must be exactly one"
    if schema_files.validate(obs, schema_files.OBSERVATION) or "episode_id" not in info:
        return f"#{i}: observation schema or info {sorted(info)}"
    if mode == "eval" and (reward != 0.0 or set(info) != INFO_KEYS):
        return f"#{i}: eval reward {reward} or info {sorted(info)}"
    return None


def _fuzz(ep) -> tuple:
    """Run FUZZ_ACTIONS seeded random actions; return (violations, number of steps).

    A new environment (alternating eval and train) replaces one that has ended, after one
    extra call on the finished episode.
    """
    ctx = {"episode_id": ep.episode_id,
           "ids": {t: [ep.record_key(t, r) for r in ep.table(t)] for t in schemas.TABLES},
           "docs": [r["doc_id"] for t in ("invoices", "payments") for r in ep.table(t)]}
    rng = Rng(FUZZ_SEED)
    bad, mode, env, prev, after_end = [], "train", None, 0, False
    for i in range(FUZZ_ACTIONS):
        if env is None or after_end:
            mode = "eval" if mode == "train" else "train"
            env, _obs, _ = _env(ep, mode)
            prev = env.max_steps
        ended = env.done
        obs, reward, _t, _u, info = env.step(_fuzz_action(rng, ctx))
        problem = _fuzz_problem(i, obs, reward, info, prev, (mode, ended))
        if problem:
            bad.append(problem)
        prev, after_end = obs["remaining_steps"], ended
    return bad, FUZZ_ACTIONS


def _page(env, table, cursor=None):
    return env.step({"action": "list_records", "table": table, "cursor": cursor})[0]["result"]


def _page_checks(ep, add) -> None:
    table = max(schemas.TABLES, key=lambda t: len(ep.table(t)))
    env, _o, _ = _env(ep)
    first = _page(env, table)
    seen, cursor, pages = [], None, 0
    while pages < 100:
        res = _page(env, table, cursor)
        seen += res["rows"]
        pages += 1
        cursor = res["next_cursor"]
        if cursor is None:
            break
    keys = [ep.record_key(table, r) for r in seen]
    add(f"a page holds at most {schemas.MAX_PAGE} rows and paging reaches every row once, in order ({table})",
        len(first["rows"]) <= schemas.MAX_PAGE and keys == [ep.record_key(table, r) for r in ep.table(table)],
        f"first page {len(first['rows'])}, paged {len(keys)} ({len(set(keys))} distinct) of {len(ep.table(table))}")
    stable = False
    if first["next_cursor"] is not None:
        one, two = _page(env, table, first["next_cursor"]), _page(env, table, first["next_cursor"])
        fresh, _o, _ = _env(ep)
        stable = bool(one) and one == two == _page(fresh, table, first["next_cursor"]) and _page(fresh, table) == first
    add("the cursor is stable: the same cursor returns the same page, also in a fresh environment", stable)
    over = env.step({"action": "list_records", "table": table, "limit": schemas.MAX_PAGE + 1})[0]
    add("a page limit above the maximum is refused with a bounded error",
        over["error"] is not None and over["error"]["code"] == "bad_args" and len(over["error"]["message"]) <= 200)


def _error_checks(ep, add) -> None:
    for label, action, code in (("an unknown ID", {"action": "get_record", "table": "invoices", "id": "no-such-id"}, "unknown_id"),
                                ("an unknown action", {"action": "drop_tables"}, "unknown_action")):
        env, _o, _ = _env(ep)
        obs = env.step(action)[0]
        err = obs["error"] or {}
        add(f"{label} gives a bounded error and spends a step",
            err.get("code") == code and len(err.get("message", "")) <= 200 and obs["remaining_steps"] == env.max_steps - 1
            and not env.done, json.dumps(obs)[:120])


def _calculator_checks(ep, add) -> None:
    env, _o, _ = _env(ep)
    ok = env.step({"action": "calculator", "expression": "(1+2)*3"})[0]
    add("the calculator evaluates a valid expression", ok["error"] is None and float(ok["result"]["value"]) == 9.0, str(ok["result"]))
    for expr in ("__import__('os')", "2**8", "1/0"):
        obs = env.step({"action": "calculator", "expression": expr})[0]
        add(f"the calculator rejects {expr}", obs["result"] is None and (obs["error"] or {}).get("code") == "calc_error", str(obs["error"]))


def _termination_checks(ep, add) -> None:
    env, _o, _ = _env(ep, "train")
    _, reward, term, trunc, _i = env.step(_submission(ep, OraclePolicy(ep.truth).findings()))
    report = env.grader_report()
    after = [env.step({"action": "calculator", "expression": "1+1"}) for _ in range(3)]
    unchanged = all(o["error"]["code"] == "episode_finished" and r == 0.0 and (t, u) == (term, trunc)
                    and o["remaining_steps"] == after[0][0]["remaining_steps"] for o, r, t, u, _ in after)
    add("after submit the episode is finished and further steps change nothing",
        term and not trunc and env.done and unchanged and env.grader_report() == report and reward == report["reward"])
    env, _o, _ = _env(ep, "train")
    early, last = [], None
    for _ in range(env.max_steps):
        last = env.step({"action": "calculator", "expression": "1"})
        early.append(last[3])
    rep = env.grader_report()
    add(f"at step {env.max_steps} (not before) the episode truncates with an empty answer",
        early[-1] and not any(early[:-1]) and not last[2] and last[0]["error"] is None
        and rep["status"] == "step_limit" and rep["n_findings"] == 0 and rep["inspection_steps"] == env.max_steps,
        f"truncated flags {early.count(True)}, status {rep['status']}, steps {rep['inspection_steps']}")
    now = [0.0]
    env, _o, _ = _env(ep, "train", time_limit_s=5.0, clock=lambda: now[0])
    env.step({"action": "calculator", "expression": "1"})
    now[0] = 6.0
    obs, _r, term, trunc, _i = env.step({"action": "calculator", "expression": "1"})
    add("the time limit on a frozen clock truncates with an empty answer",
        trunc and not term and obs["error"]["code"] == "time_limit" and env.grader_report()["status"] == "time_limit")


def _eval_checks(ep, add) -> None:
    env, _o, info = _env(ep, "eval")
    rewards, infos = [], []
    for action in ({"action": "calculator", "expression": "1"}, _submission(ep, OraclePolicy(ep.truth).findings())):
        _obs, r, _t, _u, i = env.step(action)
        rewards.append(r)
        infos.append(set(i))
    add("eval mode returns reward 0 on every step, including the last", rewards == [0.0, 0.0] and env.done, str(rewards))
    add("info carries only episode_id in eval mode, also at the end", infos == [INFO_KEYS, INFO_KEYS] and set(info) >= INFO_KEYS)
    env, _o, _ = _env(ep, "eval")
    bad = env.step(_submission(ep, [{"type": "nonsense"}]))
    add("an invalid submission scores -1", env.grader_report()["reward"] == -1 and bad[0]["error"]["code"] == "invalid_submission")
    env, _o, _ = _env(ep, "eval")
    env.step({"action": "submit", "findings": {"episode_id": "ep_foreign", "findings": []}})
    add("a foreign episode_id scores -1", env.grader_report()["reward"] == -1 and env.grader_report()["status"] == "invalid_submission")


def contract_battery(ep) -> list:
    """[(label, ok, detail)] for one episode; a group of checks that raises becomes one failed "ran to the end" row."""
    out = []
    name = ep.episode_id

    def add(label, ok, detail=""):
        out.append((f"{name}: {label}", bool(ok), "" if ok else detail))

    observations = []

    def reset(_ep, _add):
        env, obs, info = _env(ep)
        add("reset returns exactly task, manifest, policy and remaining_steps",
            set(obs) == RESET_KEYS and obs["remaining_steps"] == env.max_steps and set(info) >= INFO_KEYS, str(sorted(obs)))

    def sample(_ep, _add):
        observations.extend(_observations(ep))
        add("every later observation has only result, error and remaining_steps",
            all(set(o) == STEP_KEYS for o in observations[1:]),
            str([sorted(o) for o in observations[1:] if set(o) != STEP_KEYS]))

    def schema(_ep, _add):
        errors = [e for o in observations for e in schema_files.validate(o, schema_files.OBSERVATION)]
        add(f"all {len(observations)} sampled observations validate against observation.schema.json", not errors, "; ".join(errors[:2]))

    def fuzz(_ep, _add):
        bad, steps = _fuzz(ep)
        add(f"seeded contract fuzz ({steps} actions, reset every episode end) has 0 invariant violations",
            not bad, f"{len(bad)}: {'; '.join(bad[:2])}")

    for group in (reset, sample, _page_checks, _error_checks, _calculator_checks, _termination_checks, _eval_checks, schema, fuzz):
        try:
            group(ep, add)
        except Exception as exc:  # a broken environment fails the check instead of stopping the report
            add(f"{group.__name__.strip('_')} ran to the end", False, f"{type(exc).__name__}: {exc}"[:200])
    return out
