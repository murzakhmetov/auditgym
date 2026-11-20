"""The organizer path at scale: `python -m auditgym check --seeds-file` over the stress mix and the boundary mix.

    python tools/organizer_sweep.py OUT_DIR [CHUNK] [--record]

Run from the repository root. It takes the 300 random and 17 extreme configurations of `python -m auditgym stress`
plus one boundary configuration per edge value that auditgym/config.py accepts: no foreign currency, one and three
of them, every currency config.py accepts as base and as the only foreign one, every size, distractors all 0 and all
at 8, errors 0 and the maximum, both interacting scenarios, the twin option, period and time-zone edges, every
rounding, ID style, timestamp and row order, every single variant, minimal row counts, and every row count at 2000.
Each gets a 63-bit seed derived from its name; infeasible ones (ConfigError, for example invoice counts too large for
the 100-step budget) are skipped and listed with the reason. The contract battery runs in-process on every feasible
episode (the check itself runs it on one episode per seeds file). One seeds file per chunk of CHUNK episodes
(default 50) is checked with a host secret. OUT_DIR/sweep_summary.json keeps the exit codes, timings, FAIL lines and
tracebacks; OUT_DIR/summary.md and OUT_DIR/summary.json are deterministic (no timings), and --record also copies them
to runs/sweep/. Exit code 0 only if every chunk passes, every contract battery passes and no feasible configuration
fails to generate. Standard library only; about 15 minutes on Windows 10 with chunks of 60.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())
from auditgym import FINDING_TYPES  # noqa: E402
from auditgym.contract_battery import contract_battery  # noqa: E402
from auditgym.config import DISTRACTORS, INTERACTING, MAX_ERRORS, ROUNDINGS, ROW_ORDERS, SIZES, TS_REPRS, VARIANTS  # noqa: E402
from auditgym.config import ConfigError  # noqa: E402
from auditgym.generator import GenerationError, generate_episode  # noqa: E402
from auditgym.ids import STYLES  # noqa: E402
from auditgym.money import CURRENCY_EXPONENTS  # noqa: E402
from auditgym.stress import extreme_configs, random_configs  # noqa: E402
from auditgym.timeutil import TZ_RULES  # noqa: E402

SECRET = "sweep-host-secret-not-real"
COUNT_KEYS = ("customers", "suppliers", "sales_invoices", "purchase_invoices", "prior_invoices", "target_rows")
RECORD_DIR = Path("runs") / "sweep"


def seed_of(name: str) -> int:
    return int(hashlib.sha256(f"auditgym-sweep:{name}".encode()).hexdigest(), 16) % (2 ** 63)


def boundary_configs() -> list:
    """[(name, config)]: one configuration per boundary value config.py accepts. The name says what it tests."""
    out = [("bnd_foreign_none", {"foreign_currencies": []}),
           ("bnd_foreign_none_one_error_each_non_fx", {"foreign_currencies": [], "errors": {
               "duplicate_invoice": 1, "unallocated_payment": 1, "wrong_period": 1}}),
           ("bnd_foreign_one", {"base_currency": "EUR", "foreign_currencies": ["USD"], "errors": {"wrong_fx_rate": 2}}),
           ("bnd_foreign_three", {"base_currency": "USD", "foreign_currencies": ["EUR", "JPY", "KWD"],
                                  "errors": {"wrong_fx_rate": 2}})]
    out += [(f"bnd_base_{b}", {"base_currency": b, "errors": {"wrong_fx_rate": 1}}) for b in sorted(CURRENCY_EXPONENTS)]
    out += [(f"bnd_foreign_only_{c}", {"base_currency": "EUR" if c != "EUR" else "USD", "foreign_currencies": [c],
                                       "errors": {"wrong_fx_rate": 2}}) for c in sorted(CURRENCY_EXPONENTS)]
    out += [(f"bnd_size_{s}", {"size": s}) for s in SIZES]
    out += [("bnd_distractors_all_0", {"distractors": {k: 0 for k in DISTRACTORS}}),
            ("bnd_distractors_all_8", {"distractors": {k: 8 for k in DISTRACTORS}}),
            ("bnd_distractors_all_0_with_errors", {"distractors": {k: 0 for k in DISTRACTORS},
                                                   "errors": {t: 1 for t in FINDING_TYPES}}),
            ("bnd_distractors_all_8_large", {"size": "large", "distractors": {k: 8 for k in DISTRACTORS}})]
    out += [(f"bnd_distractor_{k}_8", {"distractors": {k: 8}}) for k in DISTRACTORS]
    out += [("bnd_errors_all_0", {"errors": {t: 0 for t in FINDING_TYPES}}),
            ("bnd_errors_max_total", {"errors": {t: MAX_ERRORS // len(FINDING_TYPES) for t in FINDING_TYPES}})]
    out += [(f"bnd_errors_{t}_max", {"errors": {t: MAX_ERRORS}}) for t in FINDING_TYPES]
    out += [(f"bnd_interacting_{i}", {"interacting": [i]}) for i in INTERACTING]
    out += [("bnd_interacting_both", {"interacting": list(INTERACTING)}),
            ("bnd_interacting_both_plus_max_errors", {"interacting": list(INTERACTING), "errors": {
                "duplicate_invoice": 2, "unallocated_payment": 2, "wrong_fx_rate": 2, "wrong_period": 2}}),
            ("bnd_twin", {"twin": True}),
            ("bnd_twin_with_errors", {"twin": True, "errors": {t: 1 for t in FINDING_TYPES}}),
            ("bnd_twin_off", {"twin": False})]
    out += [("bnd_period_first_supported", {"period": "2000-01"}), ("bnd_period_last_supported", {"period": "2100-12"}),
            ("bnd_period_year_end", {"period": "2025-12", "errors": {"wrong_period": 2}}),
            ("bnd_period_leap_february", {"period": "2028-02", "errors": {"wrong_period": 2}}),
            ("bnd_period_century_february", {"period": "2100-02"}),
            ("bnd_period_utc_wall_clock_dst_new_york", {"timezone": "America/New_York", "period": "2026-03",
                                                        "errors": {"wrong_period": 2},
                                                        "variants": {"wrong_period": ["utc_wall_clock"]}}),
            ("bnd_period_dst_end_london", {"timezone": "Europe/London", "period": "2026-10", "errors": {"wrong_period": 2}}),
            ("bnd_period_dst_start_sydney", {"timezone": "Australia/Sydney", "period": "2026-10",
                                             "errors": {"wrong_period": 2}}),
            ("bnd_period_boundary_fx_payment", {"period": "2025-09", "interacting": ["boundary_fx_payment"]})]
    out += [(f"bnd_tz_{tz}_utc_wall_clock", {"timezone": tz, "errors": {"wrong_period": 2, "wrong_fx_rate": 2},
                                              "variants": {"wrong_period": ["utc_wall_clock"], "wrong_fx_rate": ["utc_date"]}})
            for tz in TZ_RULES]
    out += [("bnd_tz_half_hour_offset_kolkata", {"timezone": "Asia/Kolkata", "errors": {"wrong_period": 2}}),
            ("bnd_tz_quarter_hour_offset_kathmandu", {"timezone": "Asia/Kathmandu", "errors": {"wrong_period": 2}}),
            ("bnd_tz_negative_offset_sao_paulo", {"timezone": "America/Sao_Paulo", "errors": {"wrong_fx_rate": 2}})]
    out += [(f"bnd_rounding_{r}", {"rounding": r}) for r in ROUNDINGS]
    out += [(f"bnd_id_style_{s}", {"id_style": s}) for s in STYLES]
    out += [(f"bnd_ts_repr_{r}", {"ts_repr": r}) for r in TS_REPRS]
    out += [(f"bnd_row_order_{o}", {"row_order": o}) for o in ROW_ORDERS]
    out += [(f"bnd_variant_{t}_{v}", {"errors": {t: 2}, "variants": {t: [v]}}) for t, vs in VARIANTS.items() for v in vs]
    out += [("bnd_counts_minimum", {"counts": {"customers": 1, "suppliers": 1, "sales_invoices": 1, "purchase_invoices": 1,
                                                "prior_invoices": 0, "target_rows": 1}}),
            ("bnd_counts_minimum_with_errors", {"counts": {"customers": 1, "suppliers": 1, "sales_invoices": 1,
                                                            "purchase_invoices": 1, "prior_invoices": 0},
                                                "errors": {"duplicate_invoice": 1}})]
    out += [(f"bnd_counts_{k}_max", {"counts": {k: 2000}}) for k in COUNT_KEYS]
    return out


def _all_configs() -> list:
    """[(group, name, config)] in a fixed order."""
    return ([("random", n, c) for n, _s, c in random_configs(300)] + [("extreme", n, c) for n, _s, c in extreme_configs()]
            + [("boundary", n, c) for n, c in boundary_configs()])


def _summary_line(lines: list) -> str:
    """The "summary:" line of a check run; its counts carry no timings."""
    return next((ln for ln in lines if ln.startswith("summary:")), "")


def _write(path: Path, text: str) -> None:
    """Write with LF line ends on every platform, so the committed summaries do not depend on the machine."""
    path.write_bytes(text.encode("utf-8"))


def _write_summaries(out: Path, entries: list, skipped: list, gen_failed: list, results: list, chunk: int,
                     record: bool = False, contract_failed: list | None = None) -> None:
    """OUT_DIR/summary.json and summary.md: configurations, infeasible ones, and per chunk episodes, exit code, summary line."""
    contract_failed = contract_failed or []
    chunks = [{"chunk": r["chunk"], "episodes": r["episodes"], "exit_code": r["rc"], "summary": r["summary_line"]}
              for r in results]
    doc = {"chunk_size": chunk, "configurations": len(entries) + len(skipped) + len(gen_failed), "feasible": len(entries),
           "infeasible": [{"name": s["name"], "reason": s["reason"]} for s in skipped],
           "generation_failures": gen_failed, "contract_failures": contract_failed,
           "configs": [{"name": e["name"], "group": e["group"], "seed": e["seed"], "chunk": i // chunk,
                        "config": e["config"]} for i, e in enumerate(entries)],
           "chunks": chunks, "all_exit_codes_zero": bool(chunks) and all(c["exit_code"] == 0 for c in chunks)}
    _write(out / "summary.json", json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    groups = {g: sum(1 for e in entries if e["group"] == g) for g in ("random", "extreme", "boundary")}
    md = ["# Organizer sweep", "",
          f"`python tools/organizer_sweep.py OUT_DIR {chunk}{' --record' if record else ''}`: the closed path (`check --seeds-file --secret-env`) over the "
          "stress mix and the boundary mix. The contract battery also ran in-process on every feasible episode "
          "(the check itself runs it on one episode per seeds file).", "",
          f"- configurations: {doc['configurations']} ({len(entries)} feasible, {len(skipped)} infeasible, "
          f"{len(gen_failed)} generation failures)",
          f"- contract battery in-process: {len(entries) - len(contract_failed)} of {len(entries)} episodes pass",
          f"- feasible by group: random {groups['random']}, extreme {groups['extreme']}, boundary {groups['boundary']}",
          f"- chunks of {chunk}: {len(chunks)}; every exit code 0: {'yes' if doc['all_exit_codes_zero'] else 'NO'}", "",
          "## Chunks", "", "| chunk | episodes | exit code | summary |", "|---|---|---|---|"]
    md += [f"| {c['chunk']} | {c['episodes']} | {c['exit_code']} | {c['summary']} |" for c in chunks]
    md += ["", "## Generation failures (accepted by config.py, GenerationError in the generator)", ""]
    md += [f"- `{g['name']}`: {g['error']}" for g in gen_failed] or ["- none"]
    md += ["", "## Contract battery failures", ""]
    md += [f"- `{c['name']}`: {c['first_failure']}" for c in contract_failed] or ["- none"]
    md += ["", "## Infeasible configurations (ConfigError, skipped)", ""]
    md += [f"- `{s['name']}`: {s['reason']}" for s in skipped] or ["- none"]
    md += ["", "## Boundary configurations that ran", ""]
    md += [f"- `{e['name']}`" for e in entries if e["group"] == "boundary"]
    _write(out / "summary.md", "\n".join(md) + "\n")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    record = "--record" in argv
    argv = [a for a in argv if a != "--record"]
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    out = Path(argv[0])
    chunk = int(argv[1]) if len(argv) > 1 else 50
    out.mkdir(parents=True, exist_ok=True)
    entries, skipped, gen_failed, contract_failed = [], [], [], []
    for group, name, cfg in _all_configs():
        seed = seed_of(name)
        try:
            gen = generate_episode(seed, cfg, secret=SECRET)
        except ConfigError as exc:
            skipped.append({"name": name, "reason": " ".join(str(exc).split())})
            continue
        except GenerationError as exc:
            gen_failed.append({"name": name, "error": " ".join(str(exc).split())[:200]})
            continue
        bad = next((f"{label} {detail}".strip() for label, ok, detail in contract_battery(gen.episode) if not ok), None)
        if bad:
            contract_failed.append({"name": name, "first_failure": " ".join(bad.split())[:200]})
        entries.append({"name": name, "group": group, "seed": seed, "config": cfg})
    print(f"{len(entries)} feasible, {len(skipped)} infeasible, {len(gen_failed)} generation failures, "
          f"{len(contract_failed)} contract failures", flush=True)
    env = dict(os.environ, SWEEP_SECRET=SECRET, PYTHONIOENCODING="utf-8")
    results = []
    for k in range(0, len(entries), chunk):
        part = [{"name": e["name"], "seed": e["seed"], "config": e["config"]} for e in entries[k:k + chunk]]
        seeds_file = out / f"chunk_{k // chunk:02d}.json"
        seeds_file.write_text(json.dumps({"split": f"sweep_{k // chunk:02d}", "episodes": part}), encoding="utf-8")
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, "-m", "auditgym", "check", "--seeds-file", str(seeds_file),
                            "--secret-env", "SWEEP_SECRET", "--out", str(out / f"out_{k // chunk:02d}")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        lines = (p.stdout + "\n" + p.stderr).splitlines()
        res = {"chunk": k // chunk, "episodes": len(part), "rc": p.returncode, "seconds": round(time.monotonic() - t0, 1),
               "summary": [ln for ln in lines if ln.startswith(("summary:", "PASS in", "FAIL in"))],
               "summary_line": _summary_line(lines),
               "fails": [ln for ln in lines if "[FAIL]" in ln][:50],
               "tracebacks": [ln for ln in lines if "Traceback" in ln or "Error:" in ln][:20],
               "stderr_tail": p.stderr[-1500:]}
        results.append(res)
        print(json.dumps({x: res[x] for x in ("chunk", "episodes", "rc", "seconds", "summary")}), flush=True)
        for ln in res["fails"][:10]:
            print("   ", ln, flush=True)
        (out / "sweep_summary.json").write_text(json.dumps({"skipped": skipped, "gen_failed": gen_failed,
                                                            "results": results}, indent=1), encoding="utf-8")
    _write_summaries(out, entries, skipped, gen_failed, results, chunk, record, contract_failed)
    if record:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("summary.md", "summary.json"):
            shutil.copyfile(out / name, RECORD_DIR / name)
    bad = [r for r in results if r["rc"] != 0]
    ok = not bad and not gen_failed and not contract_failed
    print("SWEEP", "PASS" if ok else "FAIL", f"({len(bad)} failing chunks)", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
