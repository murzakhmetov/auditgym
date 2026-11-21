"""Per-job and per-step conclusions of a GitHub Actions run, without URLs and IDs:

    gh run view RUN --json jobs,headSha | python tools/ci_jobs_json.py RUN > runs/ci/RUN.jobs.json
"""
import json
import sys

run = int(sys.argv[1])
raw = json.load(sys.stdin)
out = {
    "run": run,
    "commit": raw["headSha"],
    "made_with": f"gh run view {run} --json jobs, reduced to names, conclusions and times (URLs and IDs dropped)",
    "jobs": [
        {
            "name": j["name"],
            "conclusion": j["conclusion"],
            "started_at": j["startedAt"],
            "completed_at": j["completedAt"],
            "steps": [{"name": s["name"], "conclusion": s["conclusion"]} for s in j["steps"]],
        }
        for j in raw["jobs"]
    ],
}
sys.stdout.reconfigure(encoding="utf-8", newline="\n")
sys.stdout.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
