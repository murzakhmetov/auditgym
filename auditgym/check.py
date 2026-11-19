"""Single offline check: `python -m auditgym check`.

Sections (each a list of named pass/fail checks, see report.md):
  A. unit tests (environment contract, isolation, matcher, reward, generator, schemas)
  B. committed train/dev episodes regenerate byte-identically and verify
  C. 20 hidden-like episodes (5 clean, 5 interacting, 10 mixed): verify, run the four
     baselines plus the scripted auditor in isolated eval mode, check reward properties
  D. 20 paired checks: exact repetition, row permutation, ID remapping and timestamp
     re-rendering preserve the oracle answer and reward
  E. leak scan of every agent-visible observation
Exit code 0 only if every check passes. No network, GPU or paid API is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import time
import unittest
from pathlib import Path

from . import __version__
from . import io as aio
from .episode import load_episode
from .generator import generate_episode
from .grader import Grader
from .policies.oracle import OraclePolicy
from .report import markdown_table, miss_table, summarize
from .runner import run_many, run_one
from .splits import EPISODES_DIR, ROOT, check_set, split_entries
from .transform import transform_episode
from .verify import verify_generated

OBS_KEYS_RESET = {"task", "manifest", "policy", "remaining_steps"}
OBS_KEYS_STEP = {"result", "error", "remaining_steps"}
FORBIDDEN_IN_OBS = ("iss_", "evidence_sets", "expected_amount", "id_aliases", "provenance", "duplicate_of",
                    "rejected_attempts", "truth.json", "grader/")


class Report:
    def __init__(self):
        self.sections: dict = {}

    def add(self, section: str, name: str, ok: bool, detail="") -> bool:
        self.sections.setdefault(section, []).append({"check": name, "ok": bool(ok), "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail}" if detail and not ok else ""), flush=True)
        return ok

    @property
    def ok(self) -> bool:
        return all(c["ok"] for cs in self.sections.values() for c in cs)

    def counts(self) -> dict:
        return {s: {"passed": sum(c["ok"] for c in cs), "total": len(cs)} for s, cs in self.sections.items()}


def _digest(obj) -> str:
    return hashlib.sha256(aio.canonical_json(obj).encode("utf-8")).hexdigest()


def section_unit_tests(rep: Report) -> None:
    print("A. unit tests", flush=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    with open(ROOT / "runs" / "check" / "unittest.log", "w", encoding="utf-8", newline="\n") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    rep.add("A_unit_tests", f"unittest: {result.testsRun} tests", result.wasSuccessful(),
            f"failures={len(result.failures)} errors={len(result.errors)} (see runs/check/unittest.log)")


def section_committed(rep: Report) -> list:
    print("B. committed train/dev episodes", flush=True)
    episodes = []
    for split, e in split_entries(("train", "dev")):
        gen = generate_episode(e["seed"], e["config"])
        d = EPISODES_DIR / split / e["name"]
        same = d.exists()
        if same:
            texts = {**gen.episode.public_texts()}
            for name, text in texts.items():
                if aio.read_text(d / "public" / name) != text:
                    same = False
            for name, text in gen.episode.grader_texts().items():
                if aio.read_text(d / "grader" / name) != text:
                    same = False
        rep.add("B_committed_episodes", f"{split}/{e['name']} regenerates byte-identically", same,
                "missing or different; run `python -m auditgym build-splits`")
        ep = load_episode(d) if d.exists() else gen.episode
        v = verify_generated(ep)
        rep.add("B_committed_episodes", f"{split}/{e['name']} verifies ({len(ep.truth['issues'])} issues)", v["ok"],
                "; ".join(v["failures"][:3]))
        episodes.append((split, e["name"], ep))
    return episodes


def live_reward_properties(rep: Report, ep) -> None:
    g = Grader(ep.truth, ep.episode_id)
    eid = ep.episode_id
    oracle = OraclePolicy(ep.truth).findings()

    def r(findings, steps=0):
        return g.grade({"episode_id": eid, "findings": findings}, steps, "submitted")["reward"]

    name = ep.episode_id
    if ep.truth["issues"]:
        rep.add("C_reward", f"{name}: correct answer with evidence beats silence", r(oracle, 60) > r([], 0))
        rep.add("C_reward", f"{name}: repeating findings gains nothing", r(oracle + oracle) < r(oracle))
        f0 = oracle[0]
        mutants = {
            "guessed ids": dict(f0, affected_ids=["GUESS-1"]),
            "unsupported evidence": dict(f0, evidence_ids=f0["evidence_ids"][:1]),
            "wrong currency": dict(f0, currency="XXX" if f0["currency"] != "XXX" else "YYY"),
            "amount off by 3 tolerances": dict(f0, claimed_amount_minor=f0["claimed_amount_minor"] + 7),
        }
        for label, m in mutants.items():
            res = g.grade({"episode_id": eid, "findings": [m] + oracle[1:]}, 0, "submitted")
            rep.add("C_reward", f"{name}: {label} is not a true positive", res["tp"] == len(oracle) - 1 and res["fp"] == 1)
        aliased = []
        alias_rev = {v: k for k, v in ep.truth["id_aliases"].items()}
        for f in oracle:
            aliased.append(dict(f, affected_ids=[alias_rev.get(i, i) for i in f["affected_ids"]],
                                evidence_ids=[ep.truth["id_aliases"].get(i, i) for i in f["evidence_ids"]]))
        rep.add("C_reward", f"{name}: citing documents by alias keeps full credit", r(aliased) == 1.0)
    else:
        some = {"type": "wrong_period", "affected_ids": [ep.invoices[0]["invoice_id"]], "claimed_amount_minor": 1,
                "currency": ep.manifest["base_currency"], "evidence_ids": [ep.invoices[0]["doc_id"]], "explanation": "x"}
        rep.add("C_reward", f"{name}: silence beats a false accusation on a clean ledger", r([], 40) > r([some], 0))
    rep.add("C_reward", f"{name}: saving steps separates equal answers only slightly",
            0 < r(oracle, 10) - r(oracle, 40) <= 0.061)


def section_hidden_like(rep: Report, out_dir: Path):
    print("C. hidden-like episodes and baselines", flush=True)
    entries = check_set()
    eps = []
    t0 = time.monotonic()
    for e in entries:
        gen = generate_episode(e["seed"], e["config"])
        v = verify_generated(gen.episode, gen.clean)
        rep.add("C_data", f"{e['name']} verifies ({len(gen.episode.truth['issues'])} issues, {gen.attempts} attempt(s))", v["ok"],
                "; ".join(v["failures"][:3]))
        eps.append(("hidden_like", e["name"], gen.episode))
    rejected = sum(1 for _s, _n, ep in eps for _ in ep.provenance.get("rejected_attempts", []))
    rep.add("C_data", f"resampled attempts stay rare ({rejected} over {len(eps)} episodes)", rejected <= len(eps) // 2)
    gen_time = time.monotonic() - t0
    policies = ["random", "recon", "flag_all", "oracle", "auditor"]
    traj, grades = run_many(eps, policies, mode="eval", isolated=True)
    summary = summarize(grades)
    s = {v["policy"]: v for v in summary.values()}
    rep.add("C_reward", "oracle reaches reward 1.0 on all 20 episodes", all(g["reward"] == 1.0 for g in grades if g["policy"] == "oracle"))
    rep.add("C_reward", "flag-everything attack scores poorly (mean return <= -0.9)", s["flag_all"]["return"] <= -0.9,
            str(s["flag_all"]["return"]))
    rep.add("C_reward", "scripted auditor closes every episode (no FP, no FN)", s["auditor"]["closed_share"] == 1.0,
            str(s["auditor"]["closed_share"]))
    rep.add("C_reward", "ordering: oracle > auditor > recon > flag_all", s["oracle"]["return"] > s["auditor"]["return"]
            > s["recon"]["return"] > s["flag_all"]["return"], json.dumps({k: v["return"] for k, v in s.items()}))
    rep.add("C_reward", "random explorer stays far below the auditor", s["random"]["return"] < s["auditor"]["return"] - 0.5)
    rep.add("C_reward", "every run finishes inside 100 steps and 60 s", all(g["inspection_steps"] <= 99 and g["elapsed_s"] < 60 for g in grades))
    rep.add("C_reward", "no agent process failed", not any(g.get("agent_error") for g in grades))
    for _s, _n, ep in eps[:3] + eps[5:7]:
        live_reward_properties(rep, ep)
    return eps, traj, grades, summary, gen_time


def section_paired(rep: Report, eps: list) -> None:
    print("D. reproducibility and paired checks", flush=True)
    entries = {e["name"]: e for e in check_set()}
    for _s, name, ep in eps[:5]:
        e = entries[name]
        again = generate_episode(e["seed"], e["config"]).episode
        rep.add("D_paired", f"{name}: same seed and config regenerate identical records and answer key",
                again.public_digest() == ep.public_digest() and _digest(again.truth) == _digest(ep.truth))
    _s, name, ep = eps[1]
    a, ga = run_one(ep, "random", policy_seed=3, isolated=False)
    b, gb = run_one(ep, "random", policy_seed=3, isolated=False)
    rep.add("D_paired", f"{name}: same actions reproduce transitions and reward (random explorer)", _digest(a) == _digest(b) and ga["reward"] == gb["reward"])
    a, ga = run_one(ep, "auditor", isolated=True)
    b, gb = run_one(ep, "auditor", isolated=False)
    rep.add("D_paired", f"{name}: isolated child process and in-process runs are identical", _digest(a) == _digest(b) and ga["reward"] == gb["reward"])
    transforms = [{"permute_seed": 11, "remap_seed": 5}, {"permute_seed": 7, "remap_seed": 9, "ts_repr": "mixed"}]
    for _s, name, ep in eps[:10]:
        for tf in transforms:
            t = transform_episode(ep, **tf)
            _, g0 = run_one(ep, "oracle")
            _, g1 = run_one(t, "oracle")
            same_key = [(x["issue_id"], x["type"], x["expected_amount_minor"]) for x in ep.truth["issues"]] == \
                       [(x["issue_id"], x["type"], x["expected_amount_minor"]) for x in t.truth["issues"]]
            v = verify_generated(t)
            _, a0 = run_one(ep, "auditor", isolated=False)
            _, a1 = run_one(t, "auditor", isolated=False)
            ok = g0["reward"] == g1["reward"] == 1.0 and same_key and v["ok"] and a0["reward"] == a1["reward"]
            rep.add("D_paired", f"{name} {tf}: oracle answer and reward preserved", ok,
                    f"oracle {g0['reward']}->{g1['reward']} auditor {a0['reward']}->{a1['reward']} verify={v['failures'][:2]}")


def section_leaks(rep: Report, traj: list) -> None:
    print("E. leak scan of agent-visible observations", flush=True)
    bad_keys, bad_text = 0, 0
    for rec in traj:
        obs = rec["observation"]
        keys = set(obs)
        if keys != (OBS_KEYS_RESET if rec["step"] == 0 else OBS_KEYS_STEP):
            bad_keys += 1
        text = json.dumps(obs, ensure_ascii=False)
        if any(m in text for m in FORBIDDEN_IN_OBS):
            bad_text += 1
    rep.add("E_leaks", f"{len(traj)} observations contain only the allowed fields", bad_keys == 0, f"{bad_keys} bad")
    rep.add("E_leaks", "no answer-key markers in any observation", bad_text == 0, f"{bad_text} bad")
    rep.add("E_leaks", "oracle trajectories are never published", all(r["policy"] != "oracle" for r in traj))


def main(argv=None) -> int:
    out_dir = ROOT / "runs" / "check"
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = Report()
    t0 = time.monotonic()
    print(f"auditgym {__version__} check (offline, Python {sys.version.split()[0]})", flush=True)
    section_unit_tests(rep)
    section_committed(rep)
    eps, traj, grades, summary, gen_time = section_hidden_like(rep, out_dir)
    section_paired(rep, eps)
    section_leaks(rep, traj)
    elapsed = time.monotonic() - t0
    aio.write_jsonl(out_dir / "trajectories.jsonl", traj, ascii_only=True)
    aio.write_jsonl(out_dir / "grades.jsonl", grades, ascii_only=True)
    report = {"version": __version__, "ok": rep.ok, "elapsed_s": round(elapsed, 1), "counts": rep.counts(),
              "sections": rep.sections, "summary": summary}
    aio.write_json(out_dir / "report.json", report)
    md = [f"# auditgym check report\n", f"Result: **{'PASS' if rep.ok else 'FAIL'}** in {elapsed:.0f} s, "
          f"version {__version__}.\n", "## Checks\n"]
    for sec, cs in rep.sections.items():
        md.append(f"### {sec} ({sum(c['ok'] for c in cs)}/{len(cs)})\n")
        for c in cs:
            md.append(f"- {'PASS' if c['ok'] else 'FAIL'}: {c['check']}" + (f" ({c['detail']})" if not c["ok"] and c["detail"] else ""))
        md.append("")
    md.append("## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)\n")
    md.append(markdown_table(summary))
    md.append("## Failure analysis\n")
    md.append(miss_table(summary))
    aio.write_text(out_dir / "report.md", "\n".join(md) + "\n")
    c = rep.counts()
    print("summary:", ", ".join(f"{k} {v['passed']}/{v['total']}" for k, v in c.items()), flush=True)
    print(f"{'PASS' if rep.ok else 'FAIL'} in {elapsed:.0f} s; report: runs/check/report.md", flush=True)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
