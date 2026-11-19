# auditgym tasks

Status as of 2026-11-19 (plan: docs/PLAN.md). Done means the command in the last column passes.

| # | Step | Status | Done when |
|---|---|---|---|
| 0 | Walking skeleton | done | `python -m auditgym demo` |
| 1 | Full generator: 4 types, variants, 2 interacting scenarios, clean, distractors, twin | done | `python -m auditgym check` section B/C |
| 2 | Independent auditor and verifier with deterministic retry | done | `python -m auditgym verify DIR` |
| 3 | Env hardening, stdio isolation | done | `tests/test_env.py`, `tests/test_isolation.py` |
| 4 | Grader report, failure analysis, experimental reward | done | `tests/test_matcher.py`, `tests/test_reward.py` |
| 5 | Policies: random, recon, flag_all, oracle, auditor | done | check C_reward ordering |
| 6 | Transforms and reproducibility | done | check D_paired |
| 7 | Splits, episodes, single check, trajectories | done | `python -m auditgym check` exits 0 |
| 8 | Viewer: offline dashboard, EN/RU, dark/light, glowing evidence graph, unslop polish pass | done | `python -m auditgym viewer`, no console errors |
| 9 | Docs, LICENSE, Dockerfile, pyproject | done | README commands verified locally |
| 10 | Independent review | done | checker agent: no blocking defects; 2 point-costing (feasible configs failing on unlucky time-zone/period draws; unknown policy exiting 0) and 3 minor (agent output crashing the run, null action as timeout, calculator range) findings, all fixed and covered by tests; its scripted-child harness passes on the fixed tree |

Open items for the team:
- Build and run the Docker image once on a machine with Docker:
  `docker build -t auditgym .` then `docker run --rm --network none --cpus 2 --memory 4g auditgym`.
- Fill in the Team section of README.md.
- Optional ideas not implemented: LLM-as-judge for explanations (idea 10), a time-zone twin pair for period
  errors (idea 1, second half).
