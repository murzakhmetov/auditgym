"""Measure why recon's return fell at commit a94d9b9 (parent bb80adb); docs/DESIGN.md section 9 cites the output.

Usage: python tools/recon_drop.py [--fx N] [--mix N] [COMMIT ...]   (defaults: --fx 40 --mix 30, commits bb80adb a94d9b9)

Each commit is extracted with `git archive` into a temporary directory and measured there, in a child process that
imports that tree's auditgym, on synthetic episodes (not the committed splits):
  1. --fx N medium episodes with two wrong_fx_rate errors each (seeds 10**15+500+i). Every wrong_fx_rate target is
     counted by whether fx.csv has a rate for the document's own date and currency, and whether recon missed it. Recon
     looks a rate up by that exact date, so a document dated on a day without a published rate (a weekend or holiday:
     a94d9b9 books such documents at the latest earlier published rate) is invisible to it.
  2. --mix N clean and N error episodes (medium, one error of each type, seeds 10**15+i): recon's recall by type,
     false positives per episode and mean return.
The seeds are not paired across the two trees (the generator changed), so part 2 is a measurement, not an isolation.
Standard library only; it runs offline and writes nothing to the repository.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INNER = r'''
import json, sys
from collections import Counter
sys.path.insert(0, sys.argv[1])
from auditgym.generator import generate_episode
from auditgym.runner import run_one

n_fx, n_mix = int(sys.argv[2]), int(sys.argv[3])
out = {}
groups = {"rate_on_document_date": [0, 0], "no_rate_on_document_date": [0, 0]}  # [targets, missed by recon]
for i in range(n_fx):
    ep = generate_episode(10 ** 15 + 500 + i, {"size": "medium", "errors": {"wrong_fx_rate": 2}}).episode
    rates = {(r["date"], r["source_currency"]) for r in ep.fx}
    docs = {d["invoice_id"]: d for d in ep.invoices}
    docs.update({d["payment_id"]: d for d in ep.payments})
    _traj, g = run_one(ep, "recon", split="m", mode="eval", isolated=False)
    missed = set(g["missed_issues"])
    for t in ep.truth["issues"]:
        if t["type"] != "wrong_fx_rate":
            continue
        d = next(docs[a] for a in t["affected_ids"] if a in docs)
        stamp = d.get("timestamp") or d.get("issued_at")
        key = "rate_on_document_date" if (stamp[:10], d["currency"]) in rates else "no_rate_on_document_date"
        groups[key][0] += 1
        groups[key][1] += t["issue_id"] in missed
out["wrong_fx_rate_targets"] = {k: {"targets": v[0], "missed_by_recon": v[1]} for k, v in groups.items()}
types = ["duplicate_invoice", "unallocated_payment", "wrong_fx_rate", "wrong_period"]
for label, cfg in (("clean", {"size": "medium"}), ("errors", {"size": "medium", "errors": {t: 1 for t in types}})):
    fp = ret = 0
    missed, present = Counter(), Counter()
    for i in range(n_mix):
        ep = generate_episode(10 ** 15 + i, cfg).episode
        kinds = {t["issue_id"]: t["type"] for t in ep.truth["issues"]}
        present.update(kinds.values())
        _traj, g = run_one(ep, "recon", split="m", mode="eval", isolated=False)
        fp += g["fp"]
        ret += g["reward"]
        missed.update(kinds[m] for m in g["missed_issues"] if m in kinds)
    out[label] = {"episodes": n_mix, "mean_return": round(ret / n_mix, 3), "fp_per_episode": round(fp / n_mix, 2),
                  "recall_by_type": {t: round(1 - missed[t] / present[t], 3) for t in sorted(present)}}
print(json.dumps(out))
'''


def measure(commit: str, n_fx: int, n_mix: int) -> dict:
    data = subprocess.run(["git", "archive", "--format=tar", commit], cwd=ROOT, capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix="recon_drop_") as tmp:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(tmp, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1")
        res = subprocess.run([sys.executable, "-I", "-c", INNER, tmp, str(n_fx), str(n_mix)], cwd=tmp, env=env,
                             capture_output=True, text=True, encoding="utf-8")
        if res.returncode:
            raise SystemExit(f"error: measuring {commit} failed:\n{res.stderr[-2000:]}")
        return json.loads(res.stdout.strip().splitlines()[-1])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/recon_drop.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("commits", nargs="*", default=["bb80adb", "a94d9b9"])
    ap.add_argument("--fx", type=int, default=40, help="episodes with two wrong_fx_rate errors each")
    ap.add_argument("--mix", type=int, default=30, help="clean episodes, and as many error episodes")
    args = ap.parse_args(argv)
    result = {c: measure(c, args.fx, args.mix) for c in args.commits}
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
