"""Keep the lines of a GitHub Actions log that the README cites, so the evidence survives in the repository.

    gh run view RUN_ID --log | python tools/ci_excerpt.py RUN_ID COMMIT > runs/ci/RUN_ID.txt

Input is the tab-separated output of `gh run view --log` (job, step, timestamp and message). Kept per job: the
docker commands, the image size, every `summary:`, `unittest:` and `PASS in` line of the check (the closed-path step
included), `time` output, the fallback warning, each container-test result line, and the report lines of
`python -m auditgym.redteam --parent` (host hardening, the hardening-off control, same or separate user,
--secret-env, probe failed). Standard library only; it reads
stdin and writes stdout.
"""

from __future__ import annotations

import re
import sys

KEEP = re.compile(
    r"(^summary: |^PASS in \d+ s|^FAIL|^real\t|^##\[group\]Run (docker|python -m auditgym check|python -m auditgym\.redteam --parent|time docker|mkdir -p)"
    r"|^auditgym:\d|^auditgym:latest|warning: policy runs|\(tests\.test_container\.|^Ran \d+ tests|^OK|^FAILED"
    r"|^error: AUDITGYM_REQUIRE_AGENT_USER|^exit code \d+|\[PASS\] unittest:|^container mode: "
    r"|^\s+(host hardening: |control with host hardening off: |--secret-env[: ]"
    r"|(separate policy user|same user as the host): |probe failed))"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def excerpt(lines, run_id: str, commit: str) -> list:
    out = [f"# Excerpt of GitHub Actions run {run_id} (commit {commit}), made with tools/ci_excerpt.py.",
           f"# Full log: gh run view {run_id} --log. Format: job | step | message.", ""]
    for line in lines:
        parts = line.rstrip("\n").split("\t", 2)
        if len(parts) != 3:
            continue
        job, step, rest = parts
        msg = ANSI.sub("", rest.split(" ", 1)[1] if " " in rest else "")
        if KEEP.search(msg):
            out.append(f"{job} | {step} | {msg}")
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write("\n".join(excerpt(sys.stdin, argv[0], argv[1])) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
