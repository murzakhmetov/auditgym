"""The organizer path at scale: `python -m auditgym check --seeds-file` over the stress configuration mix.

    python tools/organizer_sweep.py OUT_DIR [CHUNK]

Run from the repository root. It takes the 300 random and 17 extreme configurations of `python -m auditgym stress`,
gives each a 63-bit seed derived from its name, skips the infeasible ones (ConfigError), writes one seeds file per
chunk of CHUNK episodes (default 50), runs the closed check on each with a host secret, and records the exit code,
the summary line and every FAIL or traceback line in OUT_DIR/sweep_summary.json. Exit code 0 only if every chunk
passes and no feasible configuration fails to generate. Standard library only; about 14 minutes on Windows 10
(six chunks of 50: 299 feasible configurations, 18 infeasible).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())
from auditgym.config import ConfigError  # noqa: E402
from auditgym.generator import GenerationError, generate_episode  # noqa: E402
from auditgym.stress import extreme_configs, random_configs  # noqa: E402

SECRET = "sweep-host-secret-not-real"


def seed_of(name: str) -> int:
    return int(hashlib.sha256(f"auditgym-sweep:{name}".encode()).hexdigest(), 16) % (2 ** 63)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    out = Path(argv[0])
    chunk = int(argv[1]) if len(argv) > 1 else 50
    out.mkdir(parents=True, exist_ok=True)
    entries, skipped, gen_failed = [], [], []
    for name, _seed, cfg in random_configs(300) + extreme_configs():
        seed = seed_of(name)
        try:
            generate_episode(seed, cfg, secret=SECRET)
        except ConfigError:
            skipped.append(name)
            continue
        except GenerationError as exc:
            gen_failed.append({"name": name, "error": str(exc)[:200]})
            continue
        entries.append({"name": name, "seed": seed, "config": cfg})
    print(f"{len(entries)} feasible, {len(skipped)} infeasible, {len(gen_failed)} generation failures", flush=True)
    env = dict(os.environ, SWEEP_SECRET=SECRET, PYTHONIOENCODING="utf-8")
    results = []
    for k in range(0, len(entries), chunk):
        part = entries[k:k + chunk]
        seeds_file = out / f"chunk_{k // chunk:02d}.json"
        seeds_file.write_text(json.dumps({"split": f"sweep_{k // chunk:02d}", "episodes": part}), encoding="utf-8")
        t0 = time.monotonic()
        p = subprocess.run([sys.executable, "-m", "auditgym", "check", "--seeds-file", str(seeds_file),
                            "--secret-env", "SWEEP_SECRET", "--out", str(out / f"out_{k // chunk:02d}")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        lines = (p.stdout + "\n" + p.stderr).splitlines()
        res = {"chunk": k // chunk, "episodes": len(part), "rc": p.returncode, "seconds": round(time.monotonic() - t0, 1),
               "summary": [ln for ln in lines if ln.startswith(("summary:", "PASS in", "FAIL in"))],
               "fails": [ln for ln in lines if "[FAIL]" in ln][:50],
               "tracebacks": [ln for ln in lines if "Traceback" in ln or "Error:" in ln][:20],
               "stderr_tail": p.stderr[-1500:]}
        results.append(res)
        print(json.dumps({x: res[x] for x in ("chunk", "episodes", "rc", "seconds", "summary")}), flush=True)
        for ln in res["fails"][:10]:
            print("   ", ln, flush=True)
        (out / "sweep_summary.json").write_text(json.dumps({"skipped": skipped, "gen_failed": gen_failed,
                                                            "results": results}, indent=1), encoding="utf-8")
    bad = [r for r in results if r["rc"] != 0]
    ok = not bad and not gen_failed
    print("SWEEP", "PASS" if ok else "FAIL", f"({len(bad)} failing chunks)", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
