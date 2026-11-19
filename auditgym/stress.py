"""Generator stress run and action-budget table (both outside `check`).

`python -m auditgym stress [--n 300]` draws N random configurations from a fixed
stream (counts are reproducible; timings and memory are not) and adds 17
extreme ones. A configuration is "infeasible" when the generator refuses it
with a ConfigError (a fixed period and time zone that cannot carry the requested
errors). Otherwise it is "generated" (an episode came back) and then either "verified"
or "verify failed"; generation that raises GenerationError is "gen failed" (any other
exception is a bug and aborts the run, traceback included). Generation time is measured in
an untraced pass; the memory peak comes from a second, tracemalloc pass. Writes runs/stress/report.md.

`python -m auditgym budget` runs the scripted auditor and the recon baseline on
the dev split at several step budgets and writes runs/budget/summary.md.
"""

from __future__ import annotations

import random
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from . import FINDING_TYPES
from . import io as aio
from .config import INTERACTING, SIZES, ConfigError
from .generator import GenerationError, generate_episode
from .timeutil import TZ_RULES

STRESS_STREAM = "auditgym-stress-v1"


def random_configs(n: int) -> list:
    rng = random.Random(STRESS_STREAM)
    out = []
    for i in range(n):
        cfg = {"size": rng.choice(sorted(SIZES)),
               "errors": {t: rng.randint(0, 2) for t in FINDING_TYPES}}
        if rng.random() < 0.5:
            cfg["timezone"] = rng.choice(sorted(TZ_RULES))
        if rng.random() < 0.5:
            cfg["period"] = f"{rng.choice([2025, 2026, 2027])}-{rng.randint(1, 12):02d}"
        inter = [x for x in INTERACTING if rng.random() < 0.3]
        if inter:
            cfg["interacting"] = inter
        out.append((f"random_{i:03d}", f"{STRESS_STREAM}:{i}", cfg))
    return out


def extreme_configs() -> list:
    """17 extreme configurations: 12 errors in every time zone, exponent mixes, year boundary, DST, size."""
    twelve = {t: 3 for t in FINDING_TYPES}
    out = []
    for tz in sorted(TZ_RULES):
        out.append((f"tz_{tz}", f"x:{tz}", {"size": "small", "timezone": tz, "errors": dict(twelve)}))
    for name, base, foreign in (("exp_jpy_kwd_bhd", "JPY", ["KWD", "BHD"]),
                                ("exp_kwd_bhd_usd", "KWD", ["BHD", "USD"]),
                                ("exp_usd_jpy_kwd", "USD", ["JPY", "KWD"])):
        out.append((name, f"x:{name}", {"size": "small", "base_currency": base, "foreign_currencies": foreign,
                                        "errors": dict(twelve)}))
    out.append(("year_boundary", "x:year", {"size": "small", "period": "2025-12", "errors": dict(twelve)}))
    out.append(("sydney_dst", "x:dst", {"size": "small", "timezone": "Australia/Sydney", "period": "2025-10",
                                        "errors": dict(twelve)}))
    out.append(("large_twelve", "x:large", {"size": "large", "errors": dict(twelve)}))
    return out


def _generate(seed, cfg: dict):
    """Returns (status, detail, gen). status is infeasible, gen_failed or generated."""
    try:
        return "generated", "", generate_episode(seed, cfg)
    except ConfigError as exc:
        return "infeasible", " ".join(str(exc).split())[:160], None
    except GenerationError as exc:
        return "gen_failed", " ".join(str(exc).split())[:160], None


def _one(seed, cfg: dict, with_auditor: bool = False, trace: bool = True) -> dict:
    rec = {"status": "generated", "attempts": 0, "gen_s": 0.0, "peak_kb": 0.0, "detail": "", "steps": None, "closed": None}
    t0 = time.monotonic()
    status, rec["detail"], gen = _generate(seed, cfg)
    rec["gen_s"] = time.monotonic() - t0
    rec["status"] = status
    if gen is not None:
        rec["attempts"] = gen.attempts
        if not gen.verification.get("ok"):
            rec["status"] = "verify_failed"
        else:
            rec["status"] = "verified"
        if with_auditor and gen.verification.get("ok"):
            from .runner import run_one

            _traj, g = run_one(gen.episode, "auditor", split="stress", mode="eval", isolated=False)
            rec["steps"], rec["closed"] = g["inspection_steps"], bool(g["closed"])
    if trace:  # separate pass: tracemalloc slows generation, so it must not feed the timing column
        tracemalloc.start()
        try:
            _generate(seed, cfg)
            rec["peak_kb"] = tracemalloc.get_traced_memory()[1] / 1024
        finally:
            tracemalloc.stop()
    return rec


def run_stress(n: int, out_dir: Path, quiet: bool = False, trace: bool = True) -> int:
    if n < 0:
        raise ValueError("--n must be >= 0")
    rows = []
    t_all = time.monotonic()
    for kind, items in (("random", random_configs(n)), ("extreme", extreme_configs())):
        for name, seed, cfg in items:
            r = _one(seed, cfg, with_auditor=(kind == "extreme"), trace=trace)
            r.update(kind=kind, name=name, config=cfg)
            rows.append(r)
    total_s = time.monotonic() - t_all

    def block(kind):
        rs = [r for r in rows if r["kind"] == kind]
        return rs, Counter(r["status"] for r in rs), Counter(r["attempts"] for r in rs if r["attempts"])

    lines = ["# auditgym stress run", "",
             f"Random stream `{STRESS_STREAM}`; counts are reproducible, timings and memory are not. "
             "Generated = verified + verify failed. Time is one untraced generation; memory is the tracemalloc peak of "
             "a second, traced generation of the same configuration.", "",
             "| set | configs | generated | verified | verify failed | infeasible | gen failed | first attempt | later attempts "
             "| max gen s | peak MB |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    ok = True
    for kind in ("random", "extreme"):
        rs, c, att = block(kind)
        lines.append(f"| {kind} | {len(rs)} | {c['verified'] + c['verify_failed']} | {c['verified']} | {c['verify_failed']} | "
                     f"{c['infeasible']} | {c['gen_failed']} | {att[1]} | "
                     f"{sum(v for k, v in att.items() if k > 1)} | {max((r['gen_s'] for r in rs), default=0):.2f} | "
                     f"{max((r['peak_kb'] for r in rs), default=0) / 1024:.1f} |")
        if c["gen_failed"] or c["verify_failed"]:
            ok = False
    ext = [r for r in rows if r["kind"] == "extreme"]
    lines += ["", "## Extreme configurations (scripted auditor, in-process)", "",
              "| name | status | attempts | gen s | auditor steps | closed |", "|---|---|---|---|---|---|"]
    for r in ext:
        lines.append(f"| {r['name']} | {r['status']} | {r['attempts']} | {r['gen_s']:.2f} | {r['steps']} | {r['closed']} |")
    infeasible = Counter(r["detail"].split(";")[0][:110] for r in rows if r["status"] == "infeasible")
    if infeasible:
        lines += ["", "## Infeasible requests (ConfigError naming what is missing)", ""]
        lines += [f"- {v} x {k}" for k, v in infeasible.most_common()]
    bad = [r for r in rows if r["status"] in ("gen_failed", "verify_failed")]
    if bad:
        lines += ["", "## Failures", ""] + [f"- {r['name']} ({r['status']}): {r['detail']} {r['config']}" for r in bad]
    lines += ["", f"Total wall time {total_s:.0f} s.", ""]
    aio.write_text(Path(out_dir) / "report.md", "\n".join(lines))
    rs, c, att = block("random")
    ec = block("extreme")[1]
    if not quiet:
        print(f"random:  {len(rs)} configs, {c['verified'] + c['verify_failed']} generated ({c['verified']} verified, "
              f"{c['verify_failed']} verify failed), {c['infeasible']} infeasible, {c['gen_failed']} gen failed; "
              f"attempts: {dict(sorted(att.items()))}")
        print(f"extreme: {len(ext)} configs, {ec['verified'] + ec['verify_failed']} generated ({ec['verified']} verified, "
              f"{ec['verify_failed']} verify failed), {ec['infeasible']} infeasible, {ec['gen_failed']} gen failed; "
              f"auditor closed {sum(1 for r in ext if r['closed'])}, max steps {max((r['steps'] or 0 for r in ext), default=0)}")
        print(f"max generation time {max((r['gen_s'] for r in rows), default=0):.2f} s (untraced), "
              f"tracemalloc peak {max((r['peak_kb'] for r in rows), default=0) / 1024:.1f} MB; "
              f"report: {Path(out_dir) / 'report.md'}")
    return 0 if ok else 1


def run_budget(budgets: list, out_dir: Path) -> int:
    from .report import markdown_table, summarize
    from .runner import run_many
    from .splits import load_split_episodes

    if not budgets or any(b < 1 for b in budgets):
        raise ValueError("--budgets must be positive integers")
    eps = load_split_episodes(("dev",))
    lines = ["# Action budget (dev, scripted auditor and recon, isolated, eval mode)", "",
             "| budget | policy | return | F1 | closed share | steps |", "|---|---|---|---|---|---|"]
    tables = []
    for b in budgets:
        _traj, grades = run_many(eps, ["auditor", "recon"], mode="eval", isolated=True, max_steps=b)
        summ = summarize(grades)
        for v in summ.values():
            lines.append(f"| {b} steps | {v['policy']} | {v['return']} | {v['f1']} | {v['closed_share']} | {v['steps']} |")
        tables.append(f"## {b} steps\n\n" + markdown_table(summ))
        print(f"max_steps {b}: " + ", ".join(f"{v['policy']} F1 {v['f1']} closed {v['closed_share']}" for v in summ.values()))
    lines += ["", f"Reproduce: `python -m auditgym budget --budgets {','.join(map(str, budgets))}` (or `make budget`).", ""]
    aio.write_text(Path(out_dir) / "summary.md", "\n".join(lines) + "\n" + "\n".join(tables))
    print(f"wrote {Path(out_dir) / 'summary.md'}")
    return 0
