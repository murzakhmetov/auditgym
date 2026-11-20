"""Single offline check: `python -m auditgym check`.

Sections (each a list of named pass/fail checks, see report.md):
  A. unit tests (environment contract, isolation, matcher, reward, generator, schemas)
  B. committed train/dev episodes regenerate byte-identically and verify;
     B_replay: the recorded actions of every committed run replay to identical
     observations and terminal rewards
  C. 20 hidden-like episodes (5 clean, 5 interacting, 10 mixed): verify, run the four
     baselines plus the scripted auditor in isolated eval mode, check reward properties
     (per-episode properties, an attack battery on every error episode, false
     accusations on every clean one)
  D. paired checks: exact repetition, same actions, isolated vs in-process runs, row
     permutation, ID remapping, timestamp re-rendering, renaming and a 28-year date shift
     preserve the oracle answer, the reward and the auditor's matched issues
  E. leak scan of every agent-visible observation
  F. in-process contract checks of the environment (contract_battery)
Exit code 0 only if every check passes (a SKIP does not fail it; counts read passed/applicable plus the skips). No network, GPU or paid API is used.

Organizer seeds: `python -m auditgym.check --seeds-file FILE [--secret-env VAR] [--out DIR]`
runs C, D, E, F (and the replay of its own runs) on the episodes of a seeds file
{"split": label, "episodes": [{"name", "seed", "config"}, ...]}. Output goes to
runs/check_closed by default and never to runs/check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
import unittest
from pathlib import Path

from . import __version__
from . import io as aio
from . import FINDING_TYPES
from .contract_battery import contract_battery
from .check_battery import clean_battery, matched_claims, replay_records, reward_battery
from . import protocol
from .episode import EpisodeFormatError, load_episode
from .config import ConfigError
from .generator import GenerationError, generate_episode
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


SAMPLING_CHECKS = ("budget_feasible", "no_surface_tells")  # verify checks about the draw; all others are correctness checks
MIN_SEED_BITS = 40  # same limit and wording as `run` (auditgym/__main__.py)
HIDDEN_LIKE_SOURCE = "public master string auditgym-check-v1"
CLOSED_OUT = ROOT / "runs" / "check_closed"
DEFAULT_OUT = ROOT / "runs" / "check"

# report.md groups the sections under the five rubric headings (section keys in report.json stay as they are).
RUBRIC = (
    ("1. Contract and isolation (25)", ("F_contract", "E_leaks")),
    ("2. Data and answer key (25)", ("B_committed_episodes", "C_data")),
    ("3. Reward reliability (25)", ("C_reward",)),
    ("4. Reproducibility (15)", ("B_replay", "D_paired")),
    ("5. Engineering and explanation (10)", ("A_unit_tests",)),
)


class Report:
    def __init__(self):
        self.sections: dict = {}
        self.seconds: dict = {}

    def add(self, section: str, name: str, ok: bool, detail="") -> bool:
        self.sections.setdefault(section, []).append({"check": name, "ok": bool(ok), "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail}" if detail and not ok else ""), flush=True)
        return ok

    def skip(self, section: str, name: str, reason: str) -> bool:
        """A check that does not apply to this set of episodes; counts as passed."""
        self.sections.setdefault(section, []).append({"check": name, "ok": True, "skipped": True, "detail": reason})
        print(f"  [SKIP] {name} - {reason}", flush=True)
        return True

    @property
    def ok(self) -> bool:
        return all(c["ok"] for cs in self.sections.values() for c in cs)

    def counts(self) -> dict:
        """Per section: passed and total count a SKIP as passed (kept as they were); applicable is the number of
        checks that ran (total minus skipped) and applicable_passed those of them that passed."""
        return {s: {"passed": sum(c["ok"] for c in cs), "total": len(cs), "skipped": sum(1 for c in cs if c.get("skipped")),
                    "applicable": sum(1 for c in cs if not c.get("skipped")),
                    "applicable_passed": sum(1 for c in cs if c["ok"] and not c.get("skipped"))}
                for s, cs in self.sections.items()}


_EPISODE_PREFIX = re.compile(r"^((ep_[0-9a-f]{6,})|((train|dev)/[A-Za-z0-9_]+)|(h\d+[A-Za-z0-9_]*))(?=[: ])")


def check_kind(label: str, names=()) -> str:
    """The property a named check tests: its label without the episode name (one of `names`, the episode names of
    this run, or a public name or episode ID), with numbers and transform dicts generalised. Most properties run once
    per episode they apply to."""
    s = label
    for name in sorted((n for n in names if n), key=len, reverse=True):
        if s.startswith(name) and s[len(name):len(name) + 1] in (":", " "):
            s = "…" + s[len(name):]
            break
    s = _EPISODE_PREFIX.sub("…", s)
    return re.sub(r"\d+", "N", re.sub(r"\{[^}]*\}", "{…}", s))


def kinds_line(rep: "Report", names=()) -> str:
    checks = [c["check"] for cs in rep.sections.values() for c in cs]
    return f"{len(checks)} named checks of {len({check_kind(c, names) for c in checks})} kinds"


def _disp(label: str) -> str:
    return "hidden-like" if label == "hidden_like" else label


def skip_note(cs=None, n=None) -> str:
    """The text ' (N skipped)' when some checks of a section did not apply (pass the check list or the count), else nothing."""
    n = sum(1 for c in cs if c.get("skipped")) if n is None else n
    return f" ({n} skipped)" if n else ""


def rejection_classes(gens: list) -> dict:
    """Count the rejected candidate attempts of generated episodes by class: sampling by exception (SampleRetry or
    BooksError), sampling by a verify check about the draw, or correctness (the auditor, evidence or integrity checks
    disagreed with the answer key). Classified by check name, never by the reason text."""
    out = {"exception": 0, "sampling_check": 0, "correctness": 0}
    for gen in gens:
        for att in gen.rejected_checks:
            failed = att["failed_checks"]
            if not failed:
                out["exception"] += 1
            elif all(n in SAMPLING_CHECKS for n in failed):
                out["sampling_check"] += 1
            else:
                out["correctness"] += 1
    return out


def correctness_rejection_check(rejected: int, classes: dict) -> tuple:
    """The C_data check that no candidate episode was rejected by a correctness check: (label, ok, detail)."""
    sampling = classes["exception"] + classes["sampling_check"]
    if classes["correctness"]:
        outcome = f"{rejected} resampled, {classes['correctness']} by a correctness check"
    else:
        outcome = f"{rejected} resampled, all for sampling reasons" if rejected else "0 resampled"
    detail = (f"{sampling} sampling (SampleRetry or BooksError {classes['exception']}, {' or '.join(SAMPLING_CHECKS)} "
              f"{classes['sampling_check']}), {classes['correctness']} correctness")
    return f"no candidate episode was rejected by a correctness check ({outcome})", not classes["correctness"], detail


def section_header(sec: str, cs: list) -> str:
    """The report.md header of one section, with the number of passed checks and the skip note."""
    ran = [c for c in cs if not c.get("skipped")]
    return f"#### {sec} ({sum(c['ok'] for c in ran)}/{len(ran)}){skip_note(cs)}\n"


def code_stamp() -> dict:
    """Evidence stamp: which code and which interpreter produced a report. code_sha256 is the sha256 of the
    canonical JSON of protocol.code_digest() without bytecode (__pycache__, .pyc, .pyo: they differ between
    machines and Python versions, while the sources are what a reader can compare). No git commit: the commit
    that holds the report cannot contain its own hash. Equal on two runs of the same code on the same machine."""
    files = {k: v for k, v in protocol.code_digest().items()
             if "/__pycache__/" not in k and not k.endswith((".pyc", ".pyo"))}
    return {"code_sha256": _digest(files), "code_files": len(files), "python": platform.python_version(),
            "platform": platform.platform()}


def stamp_line(stamp: dict) -> str:
    return f"code {stamp['code_sha256']} ({stamp['code_files']} files), Python {stamp['python']}, {stamp['platform']}"


def summary_line(rep: "Report", names=()) -> str:
    """The one-line stdout summary of every section and the coverage."""
    parts = ", ".join(f"{k} {v['applicable_passed']}/{v['applicable']}{skip_note(n=v['skipped'])}" for k, v in rep.counts().items())
    return f"summary: {parts} ({kinds_line(rep, names)})"


def _digest(obj) -> str:
    return hashlib.sha256(aio.canonical_json(obj).encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _test_id(test) -> str:
    """The id of the test method, also for a failed subTest."""
    return getattr(test, "test_case", test).id()


def section_unit_tests(rep: Report, out_dir: Path) -> None:
    print("A. unit tests", flush=True)
    t0 = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    with open(out_dir / "unittest.log", "w", encoding="utf-8", newline="\n") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    failed = {_test_id(t) for t, _ in result.failures + result.errors}
    skipped = len({_test_id(t) for t, _ in result.skipped} - failed)
    passed = result.testsRun - len(failed) - skipped
    rep.add("A_unit_tests", f"unittest: {result.testsRun} run, {passed} passed, {skipped} skipped", result.wasSuccessful(),
            f"failures={len(result.failures)} errors={len(result.errors)} (see {_rel(out_dir)}/unittest.log)")
    rep.seconds["A_unit_tests"] = time.monotonic() - t0


def section_committed(rep: Report) -> list:
    print("B. committed train/dev episodes", flush=True)
    t0 = time.monotonic()
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
    rep.seconds["B_committed_episodes"] = time.monotonic() - t0
    return episodes


REPLAY_POLICIES = ("random", "recon", "flag_all", "auditor", "silent")


def _replay_checks(rep: Report, results: dict, expected: dict) -> None:
    """expected: {(split, policy): {episode_id, ...}}; every group and episode must be present and replay."""
    for key in sorted(set(results) | set(expected)):
        split, policy = key
        r = results.get(key, {"runs": 0, "bad": [], "episodes": set()})
        bad = list(r["bad"])
        missing = sorted(expected.get(key, set()) - r["episodes"])
        if missing:
            bad.append(f"{len(missing)} expected episode(s) have no recorded run: {', '.join(missing[:3])}")
        rep.add("B_replay", f"{split}/{policy}: {r['runs']} recorded runs, each replays to identical observations and terminal reward",
                not bad, "; ".join(bad[:3]))


def section_replay_committed(rep: Report, committed: list) -> None:
    """Recorded actions of the committed train/dev runs go into a fresh AuditEnv."""
    print("B. replay of recorded actions (runs/train_dev)", flush=True)
    t0 = time.monotonic()
    path = ROOT / "runs" / "train_dev" / "trajectories.jsonl"
    if not path.exists():
        rep.add("B_replay", "runs/train_dev/trajectories.jsonl replays to identical observations", False,
                "missing; run `python -m auditgym run --out runs/train_dev`")
        return
    records = aio.read_jsonl(path)
    episodes = {(s, ep.episode_id): ep for s, _n, ep in committed}
    expected: dict = {}
    for s, _n, ep in committed:
        for p in REPLAY_POLICIES:
            expected.setdefault((s, p), set()).add(ep.episode_id)
    _replay_checks(rep, replay_records(records, episodes), expected)
    rep.seconds["B_replay"] = time.monotonic() - t0


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
            "wrong type": dict(f0, type=next(t for t in FINDING_TYPES if t != f0["type"])),
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
        for label, ok, detail, *skipped in reward_battery(ep):
            (rep.skip("C_reward", label, detail) if skipped else rep.add("C_reward", label, ok, detail))
    else:
        some = {"type": "wrong_period", "affected_ids": [ep.invoices[0]["invoice_id"]], "claimed_amount_minor": 1,
                "currency": ep.manifest["base_currency"], "evidence_ids": [ep.invoices[0]["doc_id"]], "explanation": "x"}
        rep.add("C_reward", f"{name}: silence beats a false accusation on a clean ledger", r([], 40) > r([some], 0))
        for label, ok, detail, *skipped in clean_battery(ep):
            (rep.skip("C_reward", label, detail) if skipped else rep.add("C_reward", label, ok, detail))
    rep.add("C_reward", f"{name}: saving steps separates equal answers only slightly",
            0 < r(oracle, 10) - r(oracle, 40) <= 0.061)


def section_hidden_like(rep: Report, entries: list, label: str, secret: str | None, closed: bool, pregen: dict | None = None):
    print(f"C. {_disp(label)} episodes and baselines", flush=True)
    eps, gens = [], []
    t0 = time.monotonic()
    for e in entries:
        gen = (pregen or {}).get(e["name"]) or generate_episode(e["seed"], e["config"], secret=secret)
        v = verify_generated(gen.episode, gen.clean)
        rep.add("C_data", f"{e['name']} verifies ({len(gen.episode.truth['issues'])} issues, {gen.attempts} attempt(s))", v["ok"],
                "; ".join(v["failures"][:3]))
        eps.append((label, e["name"], gen.episode))
        gens.append(gen)
    rejected = sum(1 for _s, _n, ep in eps for _ in ep.provenance.get("rejected_attempts", []))
    if closed and len(eps) < 4:
        rep.skip("C_data", f"resampled attempts stay rare ({rejected} over {len(eps)} episodes)",
                 "too few episodes for a rate; measurement only")
    else:
        rep.add("C_data", f"resampled attempts stay rare ({rejected} over {len(eps)} episodes)", rejected <= len(eps) // 2)
    classes = rejection_classes(gens)
    rep.add("C_data", *correctness_rejection_check(rejected, classes))
    gen_time = time.monotonic() - t0
    rep.seconds["C_data"] = gen_time
    t1 = time.monotonic()
    n = len(eps)
    policies = ["random", "recon", "flag_all", "silent", "oracle", "auditor"]
    traj, grades = run_many(eps, policies, mode="eval", isolated=True)
    summary = summarize(grades)
    s = {v["policy"]: v for v in summary.values()}
    err = {p: _mean(g["reward"] for g in grades if g["policy"] == p and g["n_issues"] > 0) for p in policies}
    has_err = err["oracle"] is not None
    rep.add("C_reward", f"oracle reaches reward 1.0 on all {n} episodes", all(g["reward"] == 1.0 for g in grades if g["policy"] == "oracle"))
    rep.add("C_reward", "flag-everything attack scores poorly (mean return <= -0.9)", s["flag_all"]["return"] <= -0.9,
            str(s["flag_all"]["return"]))
    rep.add("C_reward", "scripted auditor closes every episode (no FP, no FN)", s["auditor"]["closed_share"] == 1.0,
            str(s["auditor"]["closed_share"]))
    returns = json.dumps({k: v["return"] for k, v in s.items()})
    if not closed:
        rep.add("C_reward", "ordering: oracle > auditor > recon > flag_all", s["oracle"]["return"] > s["auditor"]["return"]
                > s["recon"]["return"] > s["flag_all"]["return"], returns)
    else:
        rep.add("C_reward", "ordering: oracle >= auditor over all episodes", s["oracle"]["return"] >= s["auditor"]["return"], returns)
    order_name = "ordering on error episodes only: auditor > recon >= flag_all" if not closed \
        else "ordering on error episodes only: auditor >= recon >= flag_all"
    if has_err:
        a, rc, fa = err["auditor"], err["recon"], err["flag_all"]
        rep.add("C_reward", order_name, (a > rc if not closed else a >= rc) and rc >= fa, json.dumps(err))
    else:
        rep.skip("C_reward", order_name, "the set has no error episodes")
    if has_err or not closed:
        rep.add("C_reward", "random explorer stays far below the auditor", s["random"]["return"] < s["auditor"]["return"] - 0.5)
    else:
        rep.skip("C_reward", "random explorer stays far below the auditor", "the set has no error episodes")
    if not closed:
        rep.add("C_reward", "ordering: auditor > silent", s["auditor"]["return"] > s["silent"]["return"], returns)
    elif has_err:
        rep.add("C_reward", "ordering on error episodes only: auditor > silent", err["auditor"] > err["silent"], json.dumps(err))
    else:
        rep.skip("C_reward", "ordering on error episodes only: auditor > silent", "the set has no error episodes")
    rep.add("C_reward", "every run finishes inside 100 steps and 60 s", all(g["inspection_steps"] <= 99 and g["elapsed_s"] < 60 for g in grades))
    agent_errors = [f"{g.get('policy')} on {g.get('episode_id')}: {g['agent_error']}" for g in grades if g.get("agent_error")]
    rep.add("C_reward", "no agent process failed", not agent_errors,
            "; ".join(" ".join(str(e).split())[:200] for e in agent_errors[:3]))
    for _s, _n, ep in eps:
        live_reward_properties(rep, ep)
    if not any(ep.truth["issues"] for _s, _n, ep in eps):
        rep.skip("C_reward", "attack battery on error episodes", "the set has no error episodes")
    if all(ep.truth["issues"] for _s, _n, ep in eps):
        rep.skip("C_reward", "false accusations on clean episodes", "the set has no clean episodes")
    rep.seconds["C_reward"] = time.monotonic() - t1
    return eps, traj, grades, summary, gen_time


def _pick_reps(eps: list, preferred: tuple) -> list:
    chosen = [x for p in preferred for x in eps if x[1].startswith(p + "_")]
    if len(chosen) == len(preferred):
        return chosen
    clean = [x for x in eps if not x[2].truth["issues"]]
    errs = [x for x in eps if x[2].truth["issues"]]
    out = []
    for x in clean[:1] + errs[:1] + errs[len(errs) // 2:][:1]:
        if x not in out:
            out.append(x)
    return out


def shifted_transform(ep, tf: dict):
    """(transformed episode, shift used) for a transform with "shift_years": k, trying k, then -k; (None, None) when
    neither keeps every date inside the range. The transform itself decides: it checks the range on the values it
    shifts, after any ts_repr rewrite, and a local or UTC rendering can sit on another day than the source text."""
    k0 = tf["shift_years"]
    for k in (k0, -k0):
        try:
            return transform_episode(ep, **{**tf, "shift_years": k}), k
        except ValueError as exc:
            if not str(exc).startswith(f"shift_years {k} moves "):  # only a range refusal falls back
                raise
    return None, None


def section_paired(rep: Report, eps: list, entries: list, secret: str | None) -> None:
    print("D. reproducibility and paired checks", flush=True)
    t0 = time.monotonic()
    by_name = {e["name"]: e for e in entries}
    for _s, name, ep in eps:
        e = by_name[name]
        again = generate_episode(e["seed"], e["config"], secret=secret).episode
        rep.add("D_paired", f"{name}: same seed and config regenerate identical records and answer key",
                again.public_digest() == ep.public_digest() and _digest(again.truth) == _digest(ep.truth))
    reps = _pick_reps(eps, ("h02", "h06", "h13"))
    for _s, name, ep in reps:
        a, ga = run_one(ep, "random", policy_seed=3, isolated=False)
        b, gb = run_one(ep, "random", policy_seed=3, isolated=False)
        rep.add("D_paired", f"{name}: same actions reproduce transitions and reward (random explorer)", _digest(a) == _digest(b) and ga["reward"] == gb["reward"])
    for _s, name, ep in reps:
        for pol in (("auditor", "recon") if name == reps[0][1] else ("auditor",)):
            a, ga = run_one(ep, pol, isolated=True)
            b, gb = run_one(ep, pol, isolated=False)
            suffix = "" if pol == "auditor" else " (recon)"
            rep.add("D_paired", f"{name}: isolated child process and in-process runs are identical{suffix}",
                    _digest(a) == _digest(b) and ga["reward"] == gb["reward"])
    transforms = [{"permute_seed": 11, "remap_seed": 5}, {"permute_seed": 7, "remap_seed": 9, "ts_repr": "mixed", "rename_seed": 21},
                  {"remap_seed": 3, "ts_repr": "utc"}, {"shift_years": 28},
                  {"shift_years": 28, "permute_seed": 4, "remap_seed": 6, "ts_repr": "local", "rename_seed": 8}]
    base: dict = {}
    for _s, name, ep in eps:
        _, g0 = run_one(ep, "oracle")
        t0_, a0 = run_one(ep, "auditor", isolated=False)
        base[name] = (g0, a0, matched_claims(t0_, a0))

    def paired(name, ep, tf):
        g0, a0, m0 = base[name]
        if "shift_years" in tf:  # +28 when the episode's dates allow it (late periods cannot), else -28
            t, k = shifted_transform(ep, tf)
            if t is None:
                rep.skip("D_paired", f"{name} {tf}: oracle answer and reward preserved",
                         "no 28-year shift keeps the dates inside 1901-03-01 .. 2099-12-31")
                return
            tf = {**tf, "shift_years": k}
        else:
            t = transform_episode(ep, **tf)
        _, g1 = run_one(t, "oracle")
        t1_, a1 = run_one(t, "auditor", isolated=False)
        same_key = [(x["issue_id"], x["type"], x["expected_amount_minor"]) for x in ep.truth["issues"]] == \
                   [(x["issue_id"], x["type"], x["expected_amount_minor"]) for x in t.truth["issues"]]
        v = verify_generated(t)
        m1 = matched_claims(t1_, a1)
        ok = g0["reward"] == g1["reward"] == 1.0 and same_key and v["ok"] and a0["reward"] == a1["reward"] and m0 == m1
        rep.add("D_paired", f"{name} {tf}: oracle answer and reward preserved", ok,
                f"oracle {g0['reward']}->{g1['reward']} auditor {a0['reward']}->{a1['reward']} same matched issues+amounts={m0 == m1} "
                f"verify={v['failures'][:2]}")

    for _s, name, ep in eps:
        for tf in transforms:
            paired(name, ep, tf)
    errs = [x for x in eps if x[2].truth["issues"]]
    singles = [{"permute_seed": 13}, {"remap_seed": 17}, {"rename_seed": 19}]  # the shift runs on every episode in `transforms`
    if errs:
        single_eps = []
        for x in errs[:1] + errs[len(errs) // 2:][:1]:
            if x not in single_eps:
                single_eps.append(x)
        for _s, name, ep in single_eps:
            for tf in singles:
                paired(name, ep, tf)
    else:
        rep.skip("D_paired", "single transforms on error episodes", "the set has no error episodes")
    rep.seconds["D_paired"] = time.monotonic() - t0


def section_leaks(rep: Report, traj: list) -> None:
    print("E. leak scan of agent-visible observations", flush=True)
    t0 = time.monotonic()
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
    rep.seconds["E_leaks"] = time.monotonic() - t0


def section_contract(rep: Report, eps: list) -> None:
    print("F. in-process contract checks", flush=True)
    t0 = time.monotonic()
    pick = [x for x in eps if x[2].truth["issues"]][:1] or eps[:1]
    for _s, _n, ep in pick:
        for label, ok, detail in contract_battery(ep):
            rep.add("F_contract", label, ok, detail)
    rep.seconds["F_contract"] = time.monotonic() - t0


def isolation_line() -> str:
    """One report line: did the policy child run as a separate user or as the host's user."""
    from . import protocol

    ap = None
    try:
        ap = protocol.AgentProcess("recon", 0)
        uid = ap._agent_uid
        return f"separate user (uid {uid})" if uid is not None else "the host's user (no uid switch on this machine)"
    except Exception as exc:
        return f"unknown ({type(exc).__name__})"
    finally:
        if ap is not None:
            try:
                ap.close()
            except Exception:
                pass


def load_seeds_file(path: Path) -> tuple:
    """Returns (label, entries). Raises ValueError with a readable message on a malformed file."""
    try:
        data = aio.read_json(Path(path))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read seeds file {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("episodes"), list) or not data["episodes"]:
        raise ValueError('seeds file must be {"split": label, "episodes": [{"name", "seed", "config"}, ...]}')
    label = str(data.get("split") or Path(path).stem)
    entries, seen = [], set()
    for i, e in enumerate(data["episodes"]):
        if not isinstance(e, dict) or isinstance(e.get("seed"), bool) or not isinstance(e.get("seed"), int):
            raise ValueError(f"episode {i}: needs an integer seed")
        cfg = e.get("config", {})
        if not isinstance(cfg, dict):
            raise ValueError(f"episode {i}: config must be an object")
        name = str(e.get("name") or f"e{i + 1:02d}")
        if name in seen:
            raise ValueError(f"episode {i}: duplicate name {name}")
        seen.add(name)
        entries.append({"name": name, "seed": e["seed"], "config": cfg})
    return label, entries


def _write_report(out_dir: Path, rep: Report, summary: dict, traj: list, grades: list, elapsed: float, source: str, label: str, n: int,
                  keep_runs: bool = True, names=()) -> None:
    if keep_runs:
        aio.write_jsonl(out_dir / "trajectories.jsonl", traj, ascii_only=True)
        aio.write_jsonl(out_dir / "grades.jsonl", grades, ascii_only=True)
    stamp = code_stamp()
    report = {"version": __version__, "ok": rep.ok, "elapsed_s": round(elapsed, 1), "source": source, "counts": rep.counts(),
              "code": stamp, "section_seconds": {k: round(v, 1) for k, v in rep.seconds.items()}, "sections": rep.sections,
              "summary": summary}
    aio.write_json(out_dir / "report.json", report)
    md = ["# auditgym check report\n", f"Result: **{'PASS' if rep.ok else 'FAIL'}** in {elapsed:.0f} s, version {__version__}.\n",
          f"Episodes: {source}.\n", f"Policy isolation: {isolation_line()}.\n", f"Code: {stamp_line(stamp)}.\n",
          f"Coverage: {kinds_line(rep, names)} (a kind is one property; most run on every episode they apply to).\n",
          "## Checks (grouped by rubric criterion)\n"]
    for title, keys in RUBRIC:
        present = [k for k in keys if k in rep.sections]
        if not present:
            continue
        md.append(f"### {title}\n")
        md.append("Run time: " + ", ".join(f"{k} {rep.seconds[k]:.1f} s" for k in present if k in rep.seconds) + "\n")
        for sec in present:
            cs = rep.sections[sec]
            md.append(section_header(sec, cs))
            for c in cs:
                if c.get("skipped"):
                    md.append(f"- SKIP: {c['check']} ({c['detail']})")
                else:
                    md.append(f"- {'PASS' if c['ok'] else 'FAIL'}: {c['check']}" + (f" ({c['detail']})" if not c["ok"] and c["detail"] else ""))
            md.append("")
    md.append(f"## Baselines on the {n} {_disp(label)} episodes (eval mode, isolated agent process)\n")
    md.append(markdown_table(summary))
    md.append("## Failure analysis\n")
    md.append(miss_table(summary))
    aio.write_text(out_dir / "report.md", "\n".join(md) + "\n")


def _preflight_agent_user() -> str | None:
    """In strict mode start and stop one policy child now; the error line when the host cannot run it, else None."""
    if not protocol.require_agent_user():
        return None
    try:
        protocol.AgentProcess("recon", 0).close()
    except protocol.AgentUserRequired as exc:
        return " ".join(str(exc).split())
    return None


def main(argv=None) -> int:
    """Entry point; an episode directory that breaks its published format is one error line and exit 2."""
    try:
        return _main(argv)
    except EpisodeFormatError as exc:
        print(f"error: {' '.join(str(exc).split())[:500]}", file=sys.stderr)
        return 2


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m auditgym.check", description="Single offline check (tests, data, rewards, reproducibility, contract, leaks).")
    ap.add_argument("--seeds-file", help="run sections C, D, E, F on the episodes of this JSON file instead of the public master string")
    ap.add_argument("--secret-env", help="name of the environment variable that holds the host secret for the seeds file")
    ap.add_argument("--out", help="output directory (default runs/check, or runs/check_closed with --seeds-file)")
    ap.add_argument("--keep-runs", action="store_true",
                    help="with --seeds-file: also write trajectories.jsonl and grades.jsonl (they contain the answer key of the closed set)")
    args = ap.parse_args([] if argv is None else list(argv))
    protocol.harden_host()  # Linux: non-dumpable before the secret is read (see protocol.harden_host)
    problem = _preflight_agent_user()
    if problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    closed = args.seeds_file is not None
    if closed and not args.seeds_file.strip():
        print("error: --seeds-file needs a path (is a shell variable unset?)", file=sys.stderr)
        return 2
    if args.keep_runs and not closed:
        print("error: --keep-runs needs --seeds-file", file=sys.stderr)
        return 2
    if args.secret_env and not closed:
        print("error: --secret-env needs --seeds-file", file=sys.stderr)
        return 2
    out_dir = Path(args.out) if args.out else (CLOSED_OUT if closed else DEFAULT_OUT)
    if closed and out_dir.resolve() == DEFAULT_OUT.resolve():
        print("error: a seeds-file run never writes to runs/check; choose another --out", file=sys.stderr)
        return 2
    secret = None
    pregen: dict = {}
    refused: list = []
    if closed:
        try:
            label, entries = load_seeds_file(Path(args.seeds_file))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.secret_env:
            secret = os.environ.pop(args.secret_env, None)  # a policy child started later must not inherit it
            if not secret:
                print(f"error: environment variable {args.secret_env} is not set", file=sys.stderr)
                return 2
        bits = min(abs(e["seed"]).bit_length() for e in entries)
        if secret is None and bits <= MIN_SEED_BITS:
            print(f"WARNING: no host secret and a seed of at most {MIN_SEED_BITS} bits ({bits}): small seeds can be "
                  f"recovered from public records; use 63-bit seeds and --secret-env for closed runs", file=sys.stderr)
        refused = []
        for e in entries:
            try:  # an entry the generator refuses is a named SKIP line below; the other entries are still checked
                pregen[e["name"]] = generate_episode(e["seed"], e["config"], secret=secret)
            except (ConfigError, GenerationError) as exc:
                refused.append((e["name"], f"{type(exc).__name__}: {exc}"))
        if len(refused) == len(entries):
            print(f"error: no entry of the seeds file can be generated; {refused[0][0]}: {refused[0][1]}", file=sys.stderr)
            return 2
        source = (f"seeds file {label} ({len(entries)} episodes, secret: {'yes' if secret else 'no'})" if not refused else
                  f"seeds file {label} ({len(entries)} entries: {len(entries) - len(refused)} generated, "
                  f"{len(refused)} refused, secret: {'yes' if secret else 'no'})")
        entries = [e for e in entries if e["name"] in pregen]
    else:
        label, entries = "hidden_like", check_set()
        source = HIDDEN_LIKE_SOURCE
    out_dir.mkdir(parents=True, exist_ok=True)
    rep = Report()
    t0 = time.monotonic()
    print(f"auditgym {__version__} check (offline, Python {sys.version.split()[0]}); episodes: {source}", flush=True)
    for name, why in (refused if closed else ()):
        rep.skip("C_data", f"{name}: generated from its seed and config", f"refused, {why}")
    if not closed:
        section_unit_tests(rep, out_dir)
        committed = section_committed(rep)
        section_replay_committed(rep, committed)
    eps, traj, grades, summary, _gen_time = section_hidden_like(rep, entries, label, secret, closed, pregen)
    section_paired(rep, eps, entries, secret)
    section_leaks(rep, traj)
    section_contract(rep, eps)
    if closed:
        t1 = time.monotonic()
        print("B. replay of this run's recorded actions", flush=True)
        expected: dict = {}
        for s, _n, ep in eps:
            for p in REPLAY_POLICIES:
                expected.setdefault((s, p), set()).add(ep.episode_id)
        _replay_checks(rep, replay_records(traj, {(s, ep.episode_id): ep for s, _n, ep in eps}), expected)
        rep.seconds["B_replay"] = time.monotonic() - t1
    elapsed = time.monotonic() - t0
    names = [n for _s, n, _ep in eps]
    _write_report(out_dir, rep, summary, traj, grades, elapsed, source, label, len(eps), keep_runs=(not closed) or args.keep_runs,
                  names=names)
    print(summary_line(rep, names), flush=True)
    print(f"{'PASS' if rep.ok else 'FAIL'} in {elapsed:.0f} s; report: {_rel(out_dir)}/report.md", flush=True)
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
