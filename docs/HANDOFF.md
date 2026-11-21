# Handoff: round 9 (work in progress)

For whoever continues this work in another session. Everything needed is in this branch and on GitHub.

## Where things stand

- `main` = `round7` = `c13567f` (round 8.2, version 0.3.0). CI is green on its code commit (`c3205bc`, run 44916932590)
  and on the docs commit. Tags: `r7d-checkpoint`, `r7e1-checkpoint`, `r8-checkpoint`, `r81-checkpoint`, `r82-checkpoint`.
- This branch, `round9`, starts from `c3205bc` and holds round 9, which is not on `main` yet:
  - `3156aee`: standalone `wrong_fx_rate` and `wrong_period` errors also target payments (receipts and supplier
    disbursements), version 0.4.0 (every episode is regenerated; `configs/splits.json` changed two seeds so committed
    coverage holds). See the commit message for the design.
  - this handoff note and `tools/ci_jobs_json.py`.
- Why round 9: the last simulated jury (two independent Fable 5.2 jurors scoring against `docs/CASE.md`) gave 99 and 97 on
  round 8.1. Round 8.2 fixed three of the four deductions. The fourth, "disbursements and refunds are never in an answer
  key", is what round 9 fixes. Jurors are simulated; a fresh pair usually finds one or two new small points.
- The records under `runs/` (check, mutation, sweep, tells, stress, budget, train/dev, viewer) are NOT re-recorded for
  0.4.0 on this branch yet, and the docs still describe 0.3.0. Until they are, `tests/test_mutation_smoke.py`
  (RecordedRunTests) and some record-based checks fail. That is expected.

## What is left, in order

1. Review round 9 (adversarially: answer keys of payment-side issues recomputed independently, the scripted auditor
   equal to the key on 300+ generated episodes, verify passing, determinism, and a hunt for one- or two-comparison
   shortcuts with precision >= 0.5). Fix what it finds and commit.
2. Re-record everything on the final code, from the repository root, with `PYTHONIOENCODING=utf-8 PYTHONHASHSEED=0`:

   ```bash
   python -m auditgym build-splits && git add -A episodes && python -m auditgym build-splits && git diff --exit-code -- episodes
   python -m auditgym schemas
   python -m auditgym run --episodes episodes/train episodes/dev --policies random,recon,flag_all,oracle,auditor,silent --out runs/train_dev
   python -m auditgym budget
   python -m auditgym stress --n 300
   python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells
   python tools/mutation_smoke.py OUT_DIR --jobs 4 --record
   python -m auditgym check
   python -m auditgym check --seeds-file examples/closed_seeds_example.json --no-secret --out OUT_DIR
   python -m auditgym viewer
   python -m unittest discover -s tests -t .
   python -m auditgym.redteam
   python tools/organizer_sweep.py OUT_DIR 60 --record
   ```

   The second build-splits must leave `episodes/` unchanged (determinism). The mutation run takes about 25 minutes and
   pins the sha256 of every test module, so run it after the last test edit. The sweep takes about 25 minutes; its code
   stamp must equal the check report's (`python -c "from auditgym.check import code_stamp; print(code_stamp())"`).
3. Commit code and records (one commit), push to `round7` (fast-forward), wait for CI (`gh run watch RUN --exit-status`).
4. Update the four docs (README.md, README.ru.md, docs/DESIGN.md, docs/TASKS.md) for 0.4.0: every number from the new
   records (check summary, named checks and kinds, unit tests run/passed/skipped and `PASS in`, code stamp, mutation counts,
   sweep, tells figures, stress, budget, the hidden-like and open-split tables, the demo text from `python -m auditgym demo`,
   committed coverage counts from `episodes/*/*/grader/truth.json`), the payment-side errors in the error table and the
   limitations (DESIGN section 10 "Error targets" becomes done), and a "Done in round 9" line in TASKS.md. Then the CI tables
   from the code commit's run:

   ```bash
   gh run view RUN --log | python tools/ci_excerpt.py RUN COMMIT > runs/ci/RUN.txt
   gh run view RUN --json jobs,headSha | python tools/ci_jobs_json.py RUN > runs/ci/RUN.jobs.json
   ```

   Commit the docs and the excerpt (one commit), push to `round7`, wait for CI, then fast-forward `main` to it only if both
   commits are green (`git push origin COMMIT:refs/heads/main`), and tag `r9-checkpoint`.
5. Optional: a final simulated jury (two independent scorers in fresh clones of the tag, the rubric in docs/CASE.md:
   contract and isolation 25, data and answer key 25, reward reliability 25, reproducibility 15, engineering 10).

## Rules this project follows

- Python 3.11 standard library only; the official check runs offline. LF line endings everywhere (`tests/test_hygiene.py`
  fails on a CR byte in a stamped file). Write files with an editor or a Python script, not a shell heredoc (heredocs here
  have dropped backslashes).
- Before every code commit: the unit suite and the official check pass, and a secrets scan of the staged diff finds no
  key (`sk-ant-`, `sk-...`, `AKIA`, `ghp_`, `github_pat_`). Docs-only commits skip this.
- Two commits per round: code and records first, then docs that cite that commit's CI run. Never amend a pushed commit,
  never force-push, never delete remote branches (old branches stay).
- `main` only moves to a commit whose CI is green on all six jobs (ubuntu 3.11/3.12/3.13, windows, macOS, container).
- Docs are plain and factual: every number comes from a record file; README Limitations bullets stay short (detail in
  DESIGN). README.ru.md mirrors README.md.
- Team: porosyata (Alikhan, coder; Berdiali, speaker; Merey, presentation maker). Deadline: 2026-11-22 23:59 Astana.

## Unattended record cycle on this branch (2026-11-21 22:16 local time)

The record cycle of step 2 ran on commit 3156aee (round 9 before any review) and STOPPED. Last lines of its log:

```text
=== 21:40:03 build-splits-1
=== 21:40:07 build-splits-2
=== 21:40:11 schemas
=== 21:40:11 train_dev
=== 21:40:43 train_dev-replay
=== 21:41:12 budget
=== 21:41:32 stress
=== 21:48:11 tells
=== 21:51:09 mutation-record
195 of 196 listed mutants killed; 1 survived; 0 equivalent
FAILED: mutation
killed     inject-unallocated-prior-flags-ignored
killed     config-prior-hits-not-deducted
killed     history-split-remainder-none
survived   history-paid-slots-ignore-load
killed     history-credit-dates-business-days
killed     history-credit-second-share-fixed
killed     config-prepaid-always-drawn
killed     history-split-remainder-never-prior
killed     evidence-fx-future-date
killed     evidence-period-boundary
killed     evidence-offset-start
killed     evidence-half-even
killed     protocol-max-line
killed     protocol-max-depth
killed     protocol-max-nodes
killed     protocol-separator-count
killed     protocol-max-digits
killed     protocol-max-float
killed     protocol-nonsubmit-size
killed     protocol-nan
killed     protocol-echo-length
killed     protocol-surrogate
killed     verify-stale-rate-variant
killed     shift-direction-order
killed     config-boundary-utc-date-positive
killed     inject-boundary-fallback
killed     config-boundary-fallback-refusal
killed     check-shift-direction-order
killed     shift-period-lower
killed     policy-path-append
killed     cli-keys-refusal
killed     cli-keys-fallback-unarmed
killed     protocol-cap-setuid
killed     check-no-secret-refusal
killed     env-weak-seed-bound
killed     inject-utc-wall-clock-dst
killed     protocol-host-only-info
killed     verify-key-tolerance
195 of 196 listed mutants killed; 1 survived; 0 equivalent
FAILED: mutation
```

The review of step 1 did not run (the weekly usage limit of the previous account was reached). If the review
changes code or tests, run step 2 again; otherwise continue with step 3 (these records are already committed).
