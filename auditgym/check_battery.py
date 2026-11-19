"""Grader-side attack battery and replay of recorded actions, used by `check`.

Everything here is offline and deterministic. Nothing is shown to an agent.

reward_battery(ep)   one oracle finding is changed at a time; each probe states
                     the published rule it exercises (never more than 30
                     findings or 10 evidence IDs, the schema limits).
replay_records(...)  feeds the recorded actions of each agent run into a fresh
                     AuditEnv and requires JSON-equal observations and the same
                     terminal reward (the case's "identical seeds, config,
                     version and actions reproduce transitions and rewards").
matched_claims(...)  which issues the auditor matched, with the claimed amounts.
"""

from __future__ import annotations

import json
from fractions import Fraction

from . import FINDING_TYPES
from .env import AuditEnv
from .grader import Grader
from .policies.oracle import OraclePolicy
from .reward import clip
from .schemas import MAX_EVIDENCE_IDS, MAX_FINDINGS

LADDER = (7, -7, 50, -50)


def _grade(ep, findings, steps: int = 0) -> dict:
    return Grader(ep.truth, ep.episode_id).grade({"episode_id": ep.episode_id, "findings": findings}, steps, "submitted")


def _real_doc_ids(ep) -> list:
    return sorted(d["doc_id"] for t in (ep.invoices, ep.payments) for d in t)


def _used_ids(ep) -> set:
    used = set()
    for t in ep.truth["issues"]:
        used.update(t["affected_ids"])
        for es in t["evidence_sets"]:
            used.update(es)
    return used


def reward_battery(ep) -> list:
    """[(check name, ok, detail)] for an episode with at least one issue."""
    name = ep.episode_id
    oracle = OraclePolicy(ep.truth).findings()
    n = len(oracle)
    f0 = oracle[0]
    out = []

    def add(label, ok, detail=""):
        out.append((f"{name}: {label}", bool(ok), detail))

    # Type shotgun: the same finding under every other type.
    others = [t for t in FINDING_TYPES if t != f0["type"]]
    res = _grade(ep, oracle + [dict(f0, type=t) for t in others])
    add(f"type shotgun (copies under {len(others)} other types) costs exactly {len(others)} false positives",
        res["tp"] == n and res["fp"] == len(others) and res["reward"] < 1.0, f"tp={res['tp']} fp={res['fp']}")

    # Amount ladder: neighbouring amounts, de-duplicated and clamped at 0.
    amounts = []
    for d in LADDER:
        a = max(0, f0["claimed_amount_minor"] + d)
        if a != f0["claimed_amount_minor"] and a not in amounts:
            amounts.append(a)
    res = _grade(ep, oracle + [dict(f0, claimed_amount_minor=a) for a in amounts])
    add(f"amount ladder ({len(amounts)} neighbouring amounts) costs exactly {len(amounts)} false positives",
        res["tp"] == n and res["fp"] == len(amounts) and res["reward"] < 1.0, f"tp={res['tp']} fp={res['fp']}")

    # Junk: pad the oracle answer with unmatched findings up to the 30-finding cap.
    j = MAX_FINDINGS - n
    junk = [{"type": FINDING_TYPES[i % len(FINDING_TYPES)], "affected_ids": [f"JUNK-{i}"], "claimed_amount_minor": 1 + i,
             "currency": f0["currency"], "evidence_ids": [f"JUNK-DOC-{i}"], "explanation": "x"} for i in range(j)]
    res = _grade(ep, oracle + junk)
    exact = float(clip(2 * Fraction(2 * n, 2 * n + j) - 1))
    add(f"{j} junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone",
        len(oracle + junk) == MAX_FINDINGS and res["tp"] == n and res["fp"] == j and res["reward"] == exact
        and res["reward"] < _grade(ep, oracle)["reward"], f"reward={res['reward']} expected={exact}")

    # Evidence stuffing: padding the evidence with other real documents is allowed and changes nothing.
    pad = [d for d in _real_doc_ids(ep) if d not in f0["evidence_ids"]]
    stuffed = list(f0["evidence_ids"]) + pad[:max(0, MAX_EVIDENCE_IDS - len(f0["evidence_ids"]))]
    res = _grade(ep, [dict(f0, evidence_ids=stuffed)] + oracle[1:])
    add(f"evidence padded to {len(stuffed)} IDs stays a true positive (published rule)",
        len(stuffed) <= MAX_EVIDENCE_IDS and res["tp"] == n and res["fp"] == 0 and res["reward"] == _grade(ep, oracle)["reward"],
        f"tp={res['tp']} fp={res['fp']}")

    # Right amount, wrong IDs: an unrelated but real invoice.
    used = _used_ids(ep)
    unrelated = [d["invoice_id"] for d in ep.invoices if d["invoice_id"] not in used and d["doc_id"] not in used]
    if unrelated:
        res = _grade(ep, [dict(f0, affected_ids=[unrelated[0]])] + oracle[1:])
        add("right amount with the ID of an unrelated real invoice is not a true positive",
            res["tp"] == n - 1 and res["fp"] == 1, f"tp={res['tp']} fp={res['fp']}")
    else:
        out.append((f"{name}: right amount with the ID of an unrelated real invoice is not a true positive",
                    True, "no unrelated invoice in this episode", True))
    return out


def clean_battery(ep) -> list:
    """One false accusation per finding type on a clean ledger, citing a real document."""
    name = ep.episode_id
    inv = ep.invoices[0]
    silent = _grade(ep, [])["reward"]
    out = []
    for t in FINDING_TYPES:
        f = {"type": t, "affected_ids": [inv["invoice_id"]], "claimed_amount_minor": 1, "currency": ep.manifest["base_currency"],
             "evidence_ids": [inv["doc_id"]], "explanation": "x"}
        r = _grade(ep, [f])["reward"]
        out.append((f"{name}: a {t} accusation citing a real document scores -1, below silence", r == -1.0 and r < silent, f"{r} vs {silent}"))
    return out


def matched_claims(traj: list, grade: dict) -> frozenset:
    """{(issue_id, claimed amount)} for the issues a run matched (needs the run's own submit action)."""
    findings = []
    for rec in traj or []:
        a = rec.get("action")
        if isinstance(a, dict) and a.get("action") == "submit" and isinstance(a.get("findings"), dict):
            findings = a["findings"].get("findings") or []
    return frozenset((p["issue_id"], findings[p["finding_index"]]["claimed_amount_minor"]) for p in grade.get("pairs", []))


def _j(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def infer_mode(first_obs: dict) -> str:
    text = ((first_obs.get("task") or {}).get("reward") or {}).get("returned_to_policy", "")
    return "train" if text.startswith("terminal reward") else "eval"


def replay_run(records: list, episode) -> list:
    """Replay one recorded run (list of trajectory records, step order). Returns a list of problems (empty = identical)."""
    first = records[0]["observation"]
    mode = infer_mode(first)
    # Replay with the time limit the run published, on a frozen clock: the reset observation (which states the
    # limit) must match byte for byte, and wall-clock time can never truncate a replay.
    limit = (((first.get("task") or {}).get("limits") or {}).get("time_limit_s")) or 60
    env = AuditEnv(mode=mode, max_steps=int(first["remaining_steps"]), time_limit_s=limit, clock=lambda: 0.0)
    obs, _info = env.reset(config={"episode": episode})
    problems = []
    if _j(obs) != _j(first):
        problems.append("reset observation differs")
    last = records[0]
    for rec in records[1:]:
        last = rec
        obs, reward, terminated, truncated, _info = env.step(rec["action"])
        if _j(obs) != _j(rec["observation"]):
            problems.append(f"observation differs at step {rec['step']}")
            break
        if (terminated, truncated) != (rec["terminated"], rec["truncated"]):
            problems.append(f"termination flags differ at step {rec['step']}")
            break
        if not (terminated or truncated) and reward != rec["reward"]:
            problems.append(f"reward differs at step {rec['step']}")
            break
    else:
        if not (last["terminated"] or last["truncated"]):
            problems.append("recorded run does not end")
        elif env.grader_report()["reward"] != last["reward"]:
            problems.append(f"terminal reward {env.grader_report()['reward']} != recorded {last['reward']}")
    return problems


def replay_records(records: list, episodes: dict) -> dict:
    """records: trajectory records (agent policies only); episodes: {(split, episode_id): Episode}.
    Returns {(split, policy): {"runs": n, "bad": [description, ...], "episodes": {episode_id, ...}}}."""
    # A new run starts at every step-0 record (file order), so a seed listed twice is two runs.
    open_runs: dict = {}
    runs: list = []
    for rec in records:
        key = (rec["run_id"], rec["episode_id"], rec["split"], rec["policy"])
        if rec["step"] == 0 or key not in open_runs:
            open_runs[key] = []
            runs.append((key, open_runs[key]))
        open_runs[key].append(rec)
    out: dict = {}
    for (run_id, eid, split, policy), recs in runs:
        slot = out.setdefault((split, policy), {"runs": 0, "bad": [], "episodes": set()})
        slot["runs"] += 1
        slot["episodes"].add(eid)
        ep = episodes.get((split, eid))
        if ep is None:
            slot["bad"].append(f"{eid}: episode not available")
            continue
        problems = replay_run(recs, ep)
        if problems:
            slot["bad"].append(f"{eid}: {problems[0]}")
    return out
