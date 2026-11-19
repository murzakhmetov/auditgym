# auditgym design note

auditgym is a reproducible environment for training and evaluating financial-audit agents. One episode is
one synthetic company and one reporting period. The agent reads records through five tools, then submits
findings with evidence. A grader in another process scores them against an answer key that the generator
derived from a recorded causal change. Everything runs offline on the Python 3.11 standard library.

## 1. Generation: history first, errors last

```
seed + config (+ optional host secret)
  -> resolve config (every unspecified choice drawn from the episode RNG; infeasible requests raise ConfigError)
  -> hidden history (history.py): company, customers and suppliers, invoices with line items, receipts,
     disbursements, refunds, payroll/rent/depreciation journals, FX rates with a holiday calendar
  -> error plan (inject.py): target documents created with the properties each error needs
  -> clean books      = post(history)              (books.py: the published posting rules)
  -> erroneous books  = post(history, overrides)    (same engine, so every consequence follows the rules)
  -> render (render.py): opaque random IDs, timestamps, public records; one ID map for both books
  -> answer key from the erroneous books; provenance = exact record diff clean -> erroneous
  -> independent verification (verify.py); a failing candidate is resampled from a derived seed
```

Errors are booking overrides on an error-free history (a wrong rate, a wrong posting timestamp, an allocation
cap, a second posting of the same invoice). The engine re-posts everything, so cascades stay consistent: a
receipt for an invoice booked at a wrong rate relieves the booked carrying amount and its FX difference follows.

Custom PRNG (SplitMix64, integer arithmetic only) instead of `random`, `Decimal` for money and rates, no set
iteration, LF-only UTF-8 writers. Same seed, config and version give byte-identical files on any platform.

## 2. Data contract

| File | Content |
|---|---|
| `manifest.json` | schema_version, generator_version, episode_id, company (synthetic), base_currency, currency_exponents, period_start/end, ledger_extract_end, timezone, record and document counts, rounding |
| `ledger.csv` | exactly `row_id,timestamp,account,debit_minor,credit_minor,currency,entity_id,invoice_id,payment_id`; empty field = null; base currency; one positive side |
| `invoices.jsonl` | doc_id, invoice_id, kind (sales/purchase), entity_id, issued_at, due_at, currency, total_minor, line_items[{line_no, description, quantity, unit_price_minor, amount_minor, ref}] |
| `payments.jsonl` | doc_id, payment_id, kind (receipt/disbursement/refund), entity_id or null, timestamp, currency, amount_minor, invoice_refs or null, bank_ref |
| `fx.csv` | date, source_currency, target_currency, rate (decimal string, 1 source = rate target); record ID `YYYY-MM-DD:SRC:TGT` |
| `policy.json` | UTC-offset schedule of the company time zone, period rule, FX date rule and publication calendar (holidays), conversion and rounding, posting/allocation/refund rules, journal grouping, duplicate rule, chart of accounts |
| `grader/truth.json` | issues (issue_id, type, variant, scenario, affected_ids, expected_amount_minor, currency, tolerance_minor, evidence_sets, explanation) and the doc-ID alias table |
| `grader/provenance.json` | seed, configs, attempt, history summary, injections with their semantic change, distractors, record-level ops (`add`/`remove`/`set` with before/after), clean and final digests |

Times are ISO-8601 with an offset; the same instant may be written in UTC, company time or another offset
(`ts_repr`). Local dates always come from the policy's offset schedule. Money is integer minor units with the
currency exponent (JPY 0, KWD 3, others 2). The ledger extract covers the reporting period plus a 7-day
cut-off window, with opening journals for items open at period start. IDs are opaque random tokens, unique
across tables, never sequential, and assigned the same way for injected and ordinary records.

## 3. Errors, variants, scenarios, distractors

| Type | Variants | Canonical affected_ids | Amount (base minor units) | Acceptable evidence sets |
|---|---|---|---|---|
| duplicate_invoice | same-day copy with identical line refs | both invoice_ids | one copy's posted amount | {doc A, doc B, payable row A, payable row B} or {doc A, doc B, expense row A, expense row B} |
| unallocated_payment | missing, partial | payment_id + invoice_id | amount wrongly credited to 2900 | {payment doc, invoice doc, 2900 row} |
| wrong_fx_rate | utc_date, posting_date, stale_rate, transposed | invoice_id or payment_id | abs(posted - policy amount) | {doc, primary row, fx row of the correct date} or {doc, counter row, fx row} (invoices) |
| wrong_period | booked_early, booked_late, utc_wall_clock | invoice_id or payment_id | posted primary amount | {doc, primary row} or {doc, counter row} (invoices); {doc, bank row} (payments) |

Interacting scenarios:
- `boundary_fx_payment`: a partial foreign-currency receipt just after local midnight at the period boundary
  is booked by its UTC date and UTC wall clock: wrong period and wrong FX rate on the same payment, one root
  cause.
- `fx_invoice_partial_allocation`: a foreign invoice booked at a wrong rate, then its receipt partly left in
  2900: the two errors share the invoice's receivable balance, and the receipt's relief and FX difference
  follow the wrong carrying amount.

Distractors (correct by policy): same supplier, amount and date with different line refs; recurring monthly
amounts; split payments; one receipt for two invoices; underpayments; overpayment plus refund; receipts
without invoice reference (always at least one, so a 2900 credit is never a tell by itself); documents
minutes before or after local midnight at the boundary; weekend and holiday FX; near-midnight foreign
documents converted on their local date. A twin option (`"twin": true`) rebuilds the same history with the
duplicate turned into a legitimate repeat: same ledger, opposite answer (train t03/t10).

Guards: injected monetary differences are at least 100 minor units (50 times the tolerance); FX targets fall
on dates with a published rate; unallocated targets are single-reference receipts with no other receipt on
the invoice and no legitimate excess; (type, affected_ids) is unique per episode; at most 12 errors.

## 4. Environment contract

`reset(seed, config)` returns `(observation, info)`; config is a generator config, `{"episode_dir": path}`, or
either plus `"transform"`. The first observation holds `task`, `manifest`, the full `policy`, and
`remaining_steps`. `step(action)` returns `(observation, reward, terminated, truncated, info)`.

| Action | Arguments | Result |
|---|---|---|
| list_records | table (ledger/invoices/payments/fx), cursor (null or next_cursor), limit 1..50 | rows, next_cursor, total |
| get_record | table, id | record |
| get_document | doc_id | invoice or payment document |
| calculator | expression (+ - * / parentheses, decimals; no names, no exponent) | value (decimal string) |
| submit | findings.json | accepted, findings_received |

Observations hold only `result`, `error`, and `remaining_steps`. Errors are `{code, message}` with
messages of at most 200 characters and input echoes cut at 64 characters; unexpected exceptions become
`internal_error` without a traceback. Every call consumes a step, errors included. 100 steps including the
submit; step 100 without a submit, or the 60 s limit, truncates with an empty answer. Calls after the end
return `episode_finished` and change nothing. In `train` mode the terminal reward and TP/FP/FN are returned
at the end; in `eval` mode the policy always gets 0.0 and the grader keeps everything.

## 5. Isolation and leaks

The host process holds the episode, the answer key and the grader. The policy runs as `python -m
auditgym.agent` in a child process with an empty temporary working directory, a minimal environment (no seed,
no secret, no paths) and JSON lines over stdio; reads use a thread with a deadline and a stalled child is
killed. A line that is not a well-formed action message (bad JSON, deep nesting, oversized integers, text that
cannot be encoded) becomes a bounded `unknown_action` error that consumes a step; a `null` or otherwise invalid
action goes to `step()` and gets a bounded error. A child that exits ends the episode with an empty answer
(`agent_exited`), and `run` reports it and exits non-zero. The oracle needs the answer key and runs host-side
only; its submissions never enter trajectories. Grades of a closed run stay in memory and are written after
the last episode. The task text is identical across episodes apart from the episode ID, budget and mode.
`check` scans every observation for allowed fields and answer-key markers, and `verify` scans the public files.

Policy adapters: besides the built-in baselines, any class with `act(observation, reward, info)` runs in the
child process as `module.path:ClassName` (`--policy-path DIR` for code outside the repository), so organizer
policies or model wrappers use the same isolation (`examples/custom_policy.py`). Names are validated before a
run starts; the oracle is refused in the child.

## 6. Matcher and reward

Normalization (`auditgym/matcher.py`): exact type; affected and evidence IDs trimmed, deduplicated, compared
as sets (case-sensitive); a document may be cited by doc_id or by invoice_id/payment_id (alias table);
currency upper-cased; amount within `tolerance_minor` = 2; a finding is supported when one acceptable
evidence set is a subset of its evidence IDs (extra IDs ignored). Matching is a one-to-one maximum matching
(Kuhn's algorithm); tie-break: findings in submission order, issues in issue_id order. Unmatched and
repeated findings are FP, unmatched issues FN. P, R and F1 follow the case definitions, including F1 = 1
for an empty answer on a clean episode.

Reward (`auditgym/reward.py`), computed with exact fractions: `clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)`,
where inspection_steps counts every step except the submit. Invalid structure gives -1. The experimental
reward is reported separately: per issue 0.5 for the right type and IDs, +0.25 for amount and currency,
+0.25 for evidence; softF1 = 2S / (n_findings + n_issues), so spam lowers it.

## 7. Verification of data and answer key

`python -m auditgym verify DIR` runs the named checks below. Each episode must pass them all before it is
returned by the generator.

| Check | What it proves |
|---|---|
| records_schema, ids_unique | published fields and types; IDs unique across tables |
| clean_equalities | clean books rebuilt from provenance: every journal and the trial balance balance; the independent auditor finds no discrepancy and no anomaly |
| provenance_roundtrip | applying the ops to the clean books yields the published books; reverting them yields the clean books |
| declared_discrepancies | the independent auditor (`auditor.py`, which imports no generator module) reproduces exactly the answer key: types, IDs, amounts, evidence sets |
| evidence_sufficient | a third implementation re-derives type, IDs and amount from each evidence set alone plus policy and manifest; dropping any record from a set breaks it (test) |
| budget_feasible | reading every page of every table plus the submit fits in 100 steps |
| no_surface_tells | every injected or modified row has an untouched row with the same account and null pattern |
| no_leaks | no answer-key markers or seed in public files |

## 8. Reproducibility and paired checks

`transform.py` permutes rows, remaps every ID consistently in records, answer key and provenance, and rewrites
timestamps as the same instants in another offset. Issue numbering, affected-ID order and evidence order
follow content roles, not ID strings, so the oracle answer maps one to one. `check` runs 27 such checks,
including regeneration from seed, repeated runs of the same actions, isolated versus in-process runs, and
two transforms on each of 10 episodes. Unit tests rerun generation under two `PYTHONHASHSEED` values.

## 9. Measured results

All numbers come from `python -m auditgym check` (runs/check/report.md) and `python -m auditgym run` on the
open splits (runs/train_dev/summary.md), Windows 10, Python 3.11.4, eval mode, isolated agent process.

20 hidden-like episodes (5 clean, 5 interacting, 10 mixed; seeds and configs not used in train/dev):

| Policy | Return | F1 | Steps | Closed share | FP on clean |
|---|---|---|---|---|---|
| oracle (grader-side) | 1.000 | 1.000 | 0 | 1.00 | 0 |
| auditor (scripted, full read) | 0.939 | 1.000 | 30.3 | 1.00 | 0 |
| recon (simple reconciliation) | -0.219 | 0.415 | 30.3 | 0.00 | 24 |
| random explorer (seed 0) | -1.000 | 0.000 | 15.0 | 0.00 | 10 |
| flag everything | -1.000 | 0.000 | 3.0 | 0.00 | 150 |

Open splits: auditor return 0.970 (train) and 0.947 (dev), F1 1.0 on all 20; recon -0.638 and -0.545.
Mean P and R include clean episodes, where both are 0 by definition.

Failure analysis of the recon baseline on dev (from `issues[].miss_reason` in grades.jsonl): recall 1.0 on
duplicates and unallocated receipts, but legitimate repeats and overpayments become false positives (16 on
the two clean dev episodes alone); recall 0.44 on FX and 0.38 on period errors, and every miss is
`not_flagged`: the evidence was read, but the written-date shortcut does not convert timestamps to company
time. Random and flag-all misses are `search`: they never observed a complete evidence set.

Action budget (dev, same episodes, idea 3): reading everything takes 15 to 42 pages.

| Budget | auditor F1 | auditor closed | recon F1 |
|---|---|---|---|
| 20 steps | 0.562 | 0.30 | 0.128 |
| 50 steps | 1.000 | 1.00 | 0.248 |
| 100 steps | 1.000 | 1.00 | 0.248 |

Generator robustness: 300 random configurations (random sizes, error counts 0-2 per type, time zones,
periods and interacting scenarios): 289 episodes generated and verified, 286 on the first attempt and 3 on the
second (rejections: a rate without a material transposition, an FX difference below the materiality floor,
one surface-tell rejection). The other 11 fixed a period whose boundary days fall on a weekend together with
`boundary_fx_payment`, which needs published rates on both boundary days. A stress set of 17 extreme
configurations (12 errors in each of the 11 time zones, JPY/KWD/BHD exponent mixes, year boundary, Sydney DST)
all generated on the first attempt, with the scripted auditor closing every episode in at most 49 steps
(generation at most 2.0 s, peak memory 7.5 MB).

Feasibility: an unspecified time zone or period is redrawn (on a side RNG stream, so feasible draws and the
committed episodes are unchanged) until the requested errors can be placed: a non-zero UTC offset at the
period boundary for `boundary_fx_payment` and `utc_wall_clock`-only requests, a day whose UTC date differs from
its local date for `utc_date`-only requests, weekday boundary days for `boundary_fx_payment`. Only a request
that fixes both an infeasible time zone and period fails, with a ConfigError naming what is missing; the
generator never silently injects fewer errors than requested. `check` fails if resampling of candidate
episodes exceeds half the number of episodes.

## 10. Limitations

- The Docker image was written but not built or run: the development machine has no Docker. The check itself
  ran on Windows with Python 3.11.4 and asserts byte-identical regeneration of the committed episodes, so a
  platform difference would surface as a failed check, not as silent drift.
- The generator is open source. If closed seeds come from a small space, an agent could regenerate the answer
  key by brute force. Use 63-bit random seeds, or set a host secret (`--secret-env`), which the agent process
  never receives.
- Isolation is a separate OS process with a sanitized environment, not a sandbox. Open train/dev answer keys
  sit in the repository by design, and a child running as the same OS user can still inspect its parent (for
  example the seeds-file path or environment through /proc on Linux). The host secret only stops regeneration
  from the open generator; untrusted policies, including `module:Class` adapters, need a separate OS user or
  container without the repository and the seeds file.
- The accounting model is deliberately small: base-currency ledger, payments in the invoice currency, no
  taxes, credit notes or cross-currency settlement, eleven built-in time zones instead of the IANA database.
- Explanations are not graded; the reward depends on fields and evidence only. A judge for explanations
  (idea 10) is not implemented.
- The scripted auditor shares `auditor.py` with the verifier: its perfect F1 shows that every scenario is
  solvable through the tool interface within the budget, not that an agent would reason this way.
- No model was trained, so no improvement is claimed.

## 11. Case requirements and where they are tested

| Requirement (case section 05) | Test or check |
|---|---|
| correct answer with evidence beats silence on erroneous ledgers | `tests/test_reward.py` RewardPropertyTests; check C_reward (live episodes) |
| silence beats false accusations on clean ledgers | `test_reward.py`; `tests/test_env.py` test_empty_answer_on_clean_episode_is_rewarded; check C_reward |
| duplicates gain nothing | `test_reward.py` test_duplicates_gain_nothing; `tests/test_matcher.py` test_repeated_finding_is_false_positive |
| flagging every row or type scores poorly | `test_reward.py` test_flag_everything_scores_poorly; check: flag_all mean return <= -0.9 |
| saving steps only slightly separates equal answers | `test_reward.py` test_saving_steps_only_slightly_separates_equal_answers; check C_reward |
| guessed IDs | `test_matcher.py` test_guessed_ids_score_nothing; check C_reward mutants |
| unsupported evidence | `test_matcher.py` test_incomplete_evidence_is_false_positive; `tests/test_generator.py` test_removing_a_decisive_record_breaks_the_evidence |
| currencies | `test_matcher.py` test_wrong_currency_is_false_positive |
| resubmission | `test_env.py` test_resubmission_is_ignored |
| invalid input | `test_matcher.py` test_invalid_structures; `test_env.py` test_invalid_submission_ends_with_minus_one, test_errors_are_bounded_and_consume_a_step; `tests/test_calculator.py` |
| timeouts | `test_env.py` test_time_limit_truncates, test_step_limit_truncates_with_empty_answer; `tests/test_isolation.py` test_agent_that_stalls_is_truncated |

## 12. Viewer

`python -m auditgym viewer` writes one offline HTML file for people, never for agents: no CDN, system fonts,
the graph engine inlined. It shows the policy benchmark, every open episode (the answer key labelled as the
grader view, ledger, documents, FX rates, policy), every run (the trajectory with the step at which all evidence
for an error was first seen, and the verdict with tick marks for matched, unmatched and missed) and an
Obsidian-style force graph of documents, ledger rows, FX rates, entities and accounts, with red rings on the
evidence of each error. English and Russian, dark and light. The visual pass followed the unslop skill by Damir
Sokolovsky ([@heydamir](https://x.com/heydamir), CC BY 4.0): one neutral ink ramp, one cobalt accent, no
gradients or glows in the interface chrome, and the graph as the one rich element.
