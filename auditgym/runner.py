"""Run policies on episodes.

Outputs are split by audience:
  * trajectories (agent-visible): step, action, observation, reward,
    terminated, truncated. Agent-side policies only; the oracle's submission
    is the answer key and is never written to trajectories.
  * grades (grader-only): metrics, matching details, timing, and the
    failure analysis per issue: the first step at which a complete evidence set
    had been observed, and why a missed issue was missed
    (search / not_flagged / amount / evidence).
Grades for closed runs are kept in memory and written only after every
episode has finished, so no agent process can read them during the run.
"""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path

from .diagnostics import run_diagnostics
from .env import AuditEnv
from .matcher import normalize_finding, normalize_issue
from .policies import is_external, make_policy
from .protocol import run_episode_isolated

TRAJECTORY_FIELDS = ("run_id", "split", "policy", "episode_id", "step", "action", "observation", "reward", "terminated", "truncated")


def observed_ids(obs: dict) -> set:
    out = set()
    result = (obs or {}).get("result") or {}
    recs = list(result.get("rows") or [])
    for k in ("record", "document"):
        if result.get(k):
            recs.append(result[k])
    for r in recs:
        for f in ("row_id", "doc_id", "invoice_id", "payment_id"):
            if isinstance(r.get(f), str):
                out.add(r[f])
        if "date" in r and "source_currency" in r and "target_currency" in r:
            out.add(f"{r['date']}:{r['source_currency']}:{r['target_currency']}")
    return out


def analyse(grade: dict, truth: dict, submission: list | None, seen_by_step: list | None) -> list:
    """Per-issue diagnostics (idea 4 of the case notes)."""
    aliases = truth.get("id_aliases", {})
    matched = {p["issue_id"] for p in grade.get("pairs", [])}
    nfs = [normalize_finding(i, f, aliases) for i, f in enumerate(submission or [])]
    out = []
    for t in truth.get("issues", []):
        ni = normalize_issue(t)
        first = None
        if seen_by_step is not None:
            seen = set()
            for step, ids in enumerate(seen_by_step):
                seen |= ids
                if any(es <= seen for es in ni.evidence_sets):
                    first = step
                    break
        reason = None
        if t["issue_id"] not in matched:
            same = [nf for nf in nfs if nf.type == ni.type and nf.ids == ni.ids]
            if same:
                ok_amount = [nf for nf in same if nf.currency == ni.currency and abs(nf.amount - ni.amount) <= ni.tolerance]
                reason = "evidence" if ok_amount else "amount"
            elif seen_by_step is not None and first is None:
                reason = "search"
            else:
                reason = "not_flagged"
        out.append({"issue_id": t["issue_id"], "type": t["type"], "scenario": t.get("scenario"),
                    "found": t["issue_id"] in matched, "first_full_evidence_step": first, "miss_reason": reason})
    return out


@contextlib.contextmanager
def _import_path(path: str | None):
    """Put `path` first on sys.path while an in-process policy module is imported (--policy-path)."""
    if not path:
        yield
        return
    entry = str(Path(path).resolve())
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(entry)


def run_one(episode, policy: str, *, split: str = "adhoc", mode: str = "eval", isolated: bool = True,
            policy_seed: int = 0, max_steps: int = 100, time_limit_s: float = 60.0, policy_path: str | None = None):
    """Returns (trajectory records or None for the oracle, grade record)."""
    env = AuditEnv(mode=mode, max_steps=max_steps, time_limit_s=time_limit_s)
    if not is_external(policy):
        policy_path = None  # a built-in policy never sees the directory: a file there (random.py) would shadow the standard library
    run_id = f"{split}:{policy}:{policy_seed}"
    traj = []
    submission = None
    agent_error = None
    t_start = time.monotonic()
    if policy == "oracle":
        obs, info = env.reset(config={"episode": episode})
        pol = make_policy("oracle", truth=episode.truth)
        action = pol.act(obs)
        submission = action["findings"]["findings"]
        env.step(action)
        agent_time = 0.0
        traj = None
    elif isolated:
        res = run_episode_isolated(env, {"config": {"episode": episode}}, policy, policy_seed, on_step=traj.append,
                                   policy_path=policy_path)
        agent_time = res["agent_time_s"]
        agent_error = res.get("agent_error")
    else:
        with _import_path(policy_path):  # for the whole episode, as in the child: act() may import siblings
            pol = make_policy(policy, seed=policy_seed)
            obs, info = env.reset(config={"episode": episode})
            traj.append({"step": 0, "action": None, "observation": obs, "reward": 0.0, "terminated": False, "truncated": False})
            reward, agent_time = 0.0, 0.0
            while True:
                t0 = time.monotonic()
                action = pol.act(obs, reward, info)
                agent_time += time.monotonic() - t0
                obs, reward, terminated, truncated, info = env.step(action)
                traj.append({"step": env.steps, "action": action, "observation": obs, "reward": reward,
                             "terminated": terminated, "truncated": truncated})
                if terminated or truncated:
                    break
    grade = env.grader_report()
    wall = time.monotonic() - t_start
    seen_by_step = None
    observations = None
    if traj is not None:
        for rec in traj:
            a = rec.get("action")
            if (isinstance(a, dict) and set(a) == {"action", "args"} and isinstance(a["args"], dict)
                    and "action" not in a["args"]):
                a = {"action": a["action"], **a["args"]}  # same alias flattening as env.step
            if isinstance(a, dict) and a.get("action") == "submit":
                f = a.get("findings")
                if isinstance(f, dict) and isinstance(f.get("findings"), list) and grade.get("status") == "submitted":
                    submission = f["findings"]
        if traj:
            traj[-1]["reward"] = grade["reward"]  # terminal reward filled in after the run
        seen_by_step = [observed_ids(rec["observation"]) for rec in traj]
        observations = [rec["observation"] for rec in traj]
        traj = [{"run_id": run_id, "split": split, "policy": policy, "episode_id": episode.episode_id, **rec} for rec in traj]
    record = {
        "run_id": run_id,
        "split": split,
        "policy": policy,
        "policy_seed": policy_seed,
        "episode_id": episode.episode_id,
        "mode": mode,
        "isolated": bool(isolated and policy != "oracle"),
        **grade,
        "agent_time_s": round(agent_time, 6),
        "wall_time_s": round(wall, 6),
        "agent_error": agent_error,
        "issues": analyse(grade, episode.truth, submission, seen_by_step),
        **run_diagnostics(grade, episode.truth, episode.provenance, submission, observations),
    }
    return traj, record


def run_many(episodes: list, policies: list, *, mode: str = "eval", isolated: bool = True, policy_seed: int = 0,
             max_steps: int = 100, progress=None, policy_path: str | None = None):
    """episodes: list of (split, name, Episode). Returns (trajectories, grades)."""
    trajectories, grades = [], []
    for split, name, ep in episodes:
        for pol in policies:
            traj, rec = run_one(ep, pol, split=split, mode=mode, isolated=isolated, policy_seed=policy_seed,
                                max_steps=max_steps, policy_path=policy_path)
            rec["episode_name"] = name
            if traj is not None:
                trajectories.extend(traj)
            grades.append(rec)
            if progress:
                progress(split, name, pol, rec)
    return trajectories, grades
