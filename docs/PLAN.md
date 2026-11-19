# auditgym — implementation plan

Case: `docs/CASE.md`. Deadline 2026-11-22 23:59 UTC+05:00 (≈77 h left at planning time).
Scoring is about environment and grader correctness (contract, data, reward, reproducibility). The UI earns
zero points: it is a read-only demo viewer built last.

## 1. Hard constraints

- Python 3.11, **standard library only** at runtime and for tests (`unittest`). No network, GPU, or paid API.
- 2 CPU / 4 GB RAM / 60 s per episode / 100 steps. Whole `check` run target: under 5 minutes.
- Determinism: no unordered set iteration, no wall clock in generated data, `Decimal` for FX, explicit
  rounding. Same seed + config + version + actions → byte-identical records, transitions, rewards.
- No time zone database: the policy ships an explicit UTC-offset schedule for the episode window, produced by
  our own small rule table (fixed offsets plus EU/US/AU daylight-saving rules).
- Docker is not installed on the dev machine: the Dockerfile is written but cannot be run locally (state it).

## 2. Architecture

```
            ┌────────────── grader side (host process) ───────────────┐
 seed,cfg → │ history.py → books.py → inject.py → render.py            │
            │      (hidden history → clean books → errors → public IDs)│
            │ auditor.py (independent recompute) + verify.py (self-check, retry)
            │ env.py (AuditEnv: reset/step, tools)  grader.py (matcher+reward)
            │ policies/oracle.py (needs truth, host-only)              │
            └───────────────▲──────────────────────┬──────────────────┘
                 actions    │ JSON lines (stdio)   │ observations only
            ┌───────────────┴──────────────────────▼──────────────────┐
            │ agent process: policies/{random,recon,flag_all,auditor}  │
            └──────────────────────────────────────────────────────────┘
 runner.py: trajectories.jsonl (agent-visible) + grades.jsonl (grader-only)
 transform.py: permute rows, remap IDs, re-render timestamps (paired checks)
 check.py: single command → tests, regeneration, verification, baselines, paired checks, leak scan, report
 viewer/: static offline HTML (dashboard + Obsidian-style evidence graph, EN/RU) built from episodes + runs
```

State lives in the host: episode records, truth, step counter, elapsed time. The agent process gets only
observations. In open training mode the in-process `AuditEnv` may be used directly.

## 3. Contracts

### 3.1 Episode directory

```
<episode>/public/  manifest.json ledger.csv invoices.jsonl payments.jsonl fx.csv policy.json
<episode>/grader/  truth.json provenance.json
```

- `manifest.json`: schema_version, generator_version, episode_id (opaque hash), company name (fictional),
  base_currency, currency_exponents, period_start, period_end (exclusive), cutoff_end, timezone,
  record_counts, document_counts, rounding.
- `ledger.csv`: exactly `row_id,timestamp,account,debit_minor,credit_minor,currency,entity_id,invoice_id,payment_id`.
  Empty field = null. All rows in base currency. One of debit/credit is 0. Window = [period_start, cutoff_end):
  opening journals at period_start, period postings, cut-off postings (7 days) for period-boundary evidence.
- `invoices.jsonl`: doc_id, invoice_id, kind (sales|purchase), entity_id, issued_at, due_at, currency,
  total_minor, line_items[{line_no, description, quantity, unit_price_minor, amount_minor, ref}].
- `payments.jsonl`: doc_id, payment_id, kind (receipt|disbursement|refund), entity_id|null, timestamp, currency,
  amount_minor, invoice_refs [ids]|null, bank_ref.
- `fx.csv`: date, source_currency, target_currency, rate (decimal string, 1 source = rate target). Record id
  for tools and evidence: `"{date}:{source}:{target}"`.
- `policy.json`: timezone + offset schedule; period rule; FX date rule (local calendar date of the source
  document, else latest earlier date); conversion formula and rounding mode; allocation rule; settlement rule;
  chart of accounts; duplicate rule; finding types with canonical IDs, amount convention, evidence kinds,
  tolerance.

Journal grouping (no extra ledger column): key = payment_id if set, else invoice_id if set, else timestamp.
Opening AR/AP items are booked per invoice against 3900; misc journals have unique timestamps.

### 3.2 Bookkeeping rules (policy)

- Invoice posting at `issued_at`: sales Dr 1100 / Cr 4000; purchase Dr 5000 / Cr 2000;
  base = round(total × rate(doc local date) × 10^(exp_base − exp_doc)).
- Receipt at `timestamp`: Dr 1000 conv(amount, rate(payment date)); allocate to `invoice_refs` in order, each
  up to the open balance in document currency; AR relief at booked carrying amount (proportional, last
  allocation clears the remainder); excess or null refs → Cr 2900 at payment rate; difference → 7900.
- Disbursement: mirror (Dr 2000 relief / Cr 1000 / 7900). Refund: Dr 2900 / Cr 1000.
- Payment currency equals the currency of every referenced invoice.

### 3.3 Error types, canonical answers (all amounts in base currency minor units, tolerance 2)

| type | affected_ids | amount | evidence sets (any one complete set) |
|---|---|---|---|
| duplicate_invoice | both invoice_ids | base amount of one copy's AP line | {doc A, doc B, AP row A, AP row B} or {doc A, doc B, expense row A, expense row B} |
| unallocated_payment | payment_id + referenced invoice_id | base amount wrongly left in 2900 | {payment doc, invoice doc, 2900 row} or {payment doc, invoice AR/opening row, 2900 row} |
| wrong_fx_rate | document id (invoice_id or payment_id) | abs(posted − correct) on primary line | {doc, primary row, fx row of the correct date} or {doc, counter row, fx row} (invoices) |
| wrong_period | document id | posted base amount of primary line | {doc, primary row} or {doc, counter row} |

Variants: wrong_fx_rate = utc_date | posting_date | stale_rate | transposed; wrong_period = booked_early |
booked_late | utc_wall_clock; unallocated_payment = missing | partial.
Interacting scenarios: `boundary_fx_payment` (foreign partial receipt after local midnight booked by UTC date →
wrong_period + wrong_fx_rate on one payment); `fx_invoice_partial_allocation` (invoice booked at wrong rate,
then its partial receipt partly left in 2900 → wrong_fx_rate + unallocated_payment on linked records).
Distractors: legit repeats (same supplier/amount/date, different refs), recurring monthly amounts, split
payments, multi-invoice payments, underpayments, overpayment + refund, null-ref receipts, boundary documents
(correct side of midnight), weekend/holiday FX, near-midnight FX converted on the local date.

### 3.4 truth.json / provenance.json (grader only)

- truth: schema_version, episode_id, issues[{issue_id, type, variant, scenario, affected_ids,
  expected_amount_minor, currency, tolerance_minor, evidence_sets[[ids]], explanation}].
- provenance: generator_version, config_version, seed, config, attempt, history summary, injections[{issue_ids,
  ops[{op: add|remove|set, table, id, field?, before?, after?, record?}]}], distractors, clean_digest,
  final_digest. Ops are computed by diffing clean vs injected public records under one ID map, so reverting
  them reproduces the clean books exactly.

### 3.5 Actions and observations (JSON)

```
{"action":"list_records","table":"ledger|invoices|payments|fx","cursor":null|"<str>","limit":1..50}
{"action":"get_record","table":"...","id":"..."}
{"action":"get_document","doc_id":"..."}
{"action":"calculator","expression":"(100000 / 1.0842) - 92000"}
{"action":"submit","findings":{"episode_id":"...","findings":[...]}}
```

Observation: `{step, remaining_steps, action, ok, result|null, error|null}`; reset observation adds `task`,
`manifest`, `policy`. list_records returns headers only for invoices (no line_items); full documents come from
get_document. Errors: unknown_action, bad_args, unknown_table, unknown_id, bad_cursor, calc_error,
episode_finished, invalid_submission — bounded text, input echoes truncated to 64 chars. Every step consumes
budget, including errors. `max_steps` = 100 (lower budgets allowed for experiments). Time limit 60 s →
truncated with empty answer. Steps after the end return `episode_finished` without changing the grade.
Modes: `train` returns the terminal reward (and counts) at the end; `eval` always returns reward 0 and no
diagnostics; the grader keeps them.

### 3.6 Matcher and reward

Normalization: type exact enum; IDs stripped, deduplicated, compared as sets (case-sensitive); currency
upper-case; |claimed − expected| ≤ tolerance; evidence set ⊆ cited IDs (unknown IDs ignored).
One-to-one maximum matching (Kuhn), findings in submission order, issues by issue_id. TP/FP/FN, P/R/F1 per
case rules. Reward = clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1); inspection_steps = non-submit steps.
Invalid structure (schema, limits, enum, episode_id mismatch) → −1. Experimental reward (reported apart):
soft credit 0.5 ids + 0.25 amount + 0.25 evidence, softF1 = 2S/(n_findings + n_issues).

### 3.7 Logs

- trajectories.jsonl (agent-visible): run_id, policy, split, episode_id, step, action, observation, reward,
  terminated, truncated, elapsed_ms. Step 0 = reset observation.
- grades.jsonl (grader-only): metrics, matches, unmatched reasons, missed issues with miss reason
  (search / amount / evidence / not_flagged) and first step when a complete evidence set was observed.

## 4. Steps

Executor: S = strong model (this session), M = sonnet subagent with a prompt from `docs/TASKS.md`.

| # | Step | Files (zone) | Done when (command) | Exec | h |
|---|---|---|---|---|---|
| 0 | Walking skeleton: money/time/ids utils, tiny generator (duplicate + wrong_fx_rate), env tools, matcher+reward, oracle+random, runner writes trajectories | `auditgym/{money,timeutil,ids,calculator,history,books,inject,render,generator,env,matcher,reward,grader,runner}.py`, `policies/` | `python -m auditgym demo` → oracle reward 1.0, trajectories written; `python -m unittest` green | S | 3 |
| 1 | Full generator: 4 types, variants, 2 interacting scenarios, clean, distractors, provenance by diff, truth | `history,books,inject,render,generator` | `python -m auditgym verify --random 200` all pass | S | 4 |
| 2 | Independent auditor + verifier with deterministic retry | `auditor.py, verify.py` | clean episodes → 0 discrepancies; injected → exactly truth | S | 3 |
| 3 | Env hardening: limits, errors, modes, time limit; stdio protocol + subprocess agent | `env.py, protocol.py, agent.py` | `tests/test_env.py`, `tests/test_isolation.py` green | S | 2 |
| 4 | Grader report + failure analysis + experimental reward | `grader.py, report.py` | `tests/test_matcher.py`, `tests/test_reward.py` (attack cases) green | S | 2 |
| 5 | Policies: random, recon (simple heuristics), flag_all, oracle, auditor (strong scripted) | `policies/*` | dev summary: oracle 1.0 > auditor > recon > random, flag_all ≤ −0.9 | S | 2.5 |
| 6 | Transform + reproducibility + paired checks | `transform.py, tests/test_repro.py` | paired oracle rewards equal; repeated runs byte-identical | S | 1.5 |
| 7 | Splits, committed episodes, single `check` command, sample trajectories | `configs/, episodes/, runs/, check.py` | `python -m auditgym check` exit 0 in < 5 min | S | 2 |
| 8 | Viewer (offline single HTML, Obsidian-style evidence graph) | `auditgym/viewer/*` | `python -m auditgym viewer` → `viewer/index.html` opens offline, no console errors | M | 3 |
| 9 | Docs: README (container + one command), DESIGN.md (design note, measured failure analysis, limitations), LICENSE, Dockerfile, pyproject | root, `docs/` | README commands copy-paste run | S | 1.5 |
| 10 | Independent review (checker agent) and fixes | — | checker reports no blocking issue | S | 1.5 |

## 5. Changes after independent critique (Plan agent + advisor)

- Oracle runs and all grades go to grader-only output; published `trajectories.jsonl` holds agent-side
  policies only. Closed episodes stay in memory; grader files are written after the whole run.
- Observations carry only `result`, `error`, `remaining_steps` (reset adds `task`, `manifest`, `policy`).
  No step index or action echo. Unexpected exceptions become a bounded `internal_error`.
- Matcher accepts ID aliases: a document may be cited by doc_id or by invoice_id/payment_id in both
  affected_ids and evidence_ids (published alias rule, alias table in truth.json).
- Custom PRNG on 64-bit integer arithmetic (no `random` module algorithms, no transcendental floats), so
  generation is identical across Python builds and platforms; LF-only writers; `.gitattributes`.
- Determinism contract excludes wall-clock fields: timing lives in grades only; run_id is deterministic.
  Tests rerun under two `PYTHONHASHSEED` values.
- Materiality floor: injected monetary differences ≥ 100 minor units (50× the tolerance).
- FX targets only on dates with a published rate; the policy publishes the rate calendar (holidays).
  Local dates come from the policy's offset schedule, never from the written offset.
- Evidence-only checker: each evidence set plus policy and manifest must re-derive type, IDs, and amount.
  unallocated_payment targets: single-ref receipts, no other receipts on the invoice, no legitimate excess.
- Surface-tell check: every injected row has a legitimate twin with the same account and null pattern.
- Issue numbering, affected_ids order and evidence order follow content roles, never ID strings, so paired
  transforms (row permutation, ID remap, timestamp re-rendering) keep the oracle answer. Transforms are
  available as reset options and as a CLI.
- Optional host secret mixed into the RNG: with it, an agent holding the open generator and a guessed seed
  still cannot regenerate the answer key. Closed seeds should be ≥ 64-bit random.
- Static budget check: reading every table page plus submit must fit in 100 steps.
- Jury CLI: `generate`, `verify DIR`, `run`, `grade`, `transform`, `check`.
- Kept despite the "cut" advice: viewer (requested by the user, built last by a subagent), DST rules,
  experimental reward, strong scripted `auditor` policy (demo and solvability evidence).

Sum ≈ 26 h, +30 % ≈ 34 h < 77 h left. Cut order if late: viewer polish → experimental reward → stale_rate /
transposed variants. Never cut: isolation, verification, matcher tests, check command.
