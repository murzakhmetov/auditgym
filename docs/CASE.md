# Case: RL environments for financial audit model fine-tuning

REC GENESIS HACKATHON // FINTECH // ONLINE SELECTION. Teams of 2–4, online, November 19–22, 2026.
Submission deadline: November 22, 2026, 23:59 Astana time (UTC+05:00).

> Build a reproducible simulator for an AI auditor: synthetic company documents, investigation tools,
> hidden financial errors, and a reward function.

## 01 The challenge

The agent reviews records, chooses actions, and submits findings with evidence. The environment scores
the result. Build an environment for possible model fine-tuning, not a payment app, a chatbot, or a single
audit report. Required: an RL interface, recorded trajectories, and a quality evaluation. Weight training is
optional, earns no points by itself, and must not depend on paid APIs or GPUs. No claims of model improvement
without a controlled comparison on held-out data.

## 02 Where the difficulty lies

- Four error types, independently configurable: duplicate invoices; missing or partial payment allocation;
  wrong date or exchange rate; wrong reporting period assignment.
- Interacting errors: two scenarios, for example a partial payment in another currency at a period boundary.
- Clean cases: clean companies and plausible correct distractors: split payments, refunds, legitimate
  recurring amounts.

First build a consistent hidden company history, then the documents, then the errors with a recorded causal
change. The answer key must describe the real discrepancy and the available evidence, not a random suspicious
line. Do not require facts that are unavailable. Vary names, IDs, order, amounts, currencies, time zones, and
error combinations. Difficulty should require evidence analysis and block simple tricks, but must not make the
task unsolvable.

## 03 Episode and data format

An episode is one company and one reporting period. Suggested size: 200–2,000 ledger entries, 20–200
documents, 0–12 errors.

- manifest.json: schema_version, episode_id, base_currency, period_start/end, timezone, record/document
  counts, rounding rules.
- Time is ISO-8601 with offset; money is integer minor units with the currency's exponent; FX rates are
  decimal strings. Different currencies may not be compared without conversion.

Open records:
- ledger.csv: row_id, timestamp, account, debit_minor, credit_minor, currency, entity_id, invoice_id, payment_id.
- invoices.jsonl: doc_id, invoice_id, entity_id, issued_at, due_at, currency, total_minor, line_items.
- payments.jsonl: doc_id, payment_id, timestamp, currency, amount_minor, invoice_refs.
- fx.csv: date, source_currency, target_currency, rate.
- policy.json: exchange-rate date selection, period boundaries, and rounding.

Missing references are explicit nulls, never guessed links.

Closed grader files: truth.json (issue_id, type, affected_ids, expected_amount_minor, currency, acceptable
evidence sets); provenance.json (generation history and injected changes). The agent never sees these files
or the seed. The grader runs outside the agent's process; records are readable only through a narrow tool
interface. The answer key must not leak through observations, paths, errors, debug info, or reward
explanations during a closed run.

## 04 Observations, actions, termination

- reset(seed, config) returns (observation, info). The first observation contains the task, manifest, brief
  policy, and remaining budget.
- step(action) returns (observation, reward, terminated, truncated, info). JSON-compatible contract in the
  Gymnasium style; inheriting from a Python Env is not required.
- Identical seed, config, version, and actions must reproduce records, transitions, and rewards. Reset
  isolates episode state.
- Actions: list_records(table, cursor, limit); get_record(table, id); get_document(doc_id);
  calculator(expression); submit(findings). A page holds at most 50 rows; cursors are stable.
- Calculator allows only arithmetic and decimal numbers, not code or files.
- An unknown ID or action returns a bounded error and consumes a step.
- Observation contains only the requested records, the result or error, and the remaining steps. No free
  shell, SQL, filesystem, or internet.
- Maximum 100 steps, including submit. submit ends the episode with terminated=true. A step or time limit
  gives truncated=true and an empty final answer.
- Exploration gives zero reward. Only in open training mode is the terminal reward returned to the policy;
  during evaluation, reward and diagnostics stay with the grader until the run ends. No per-step hints.

## 05 Findings and reward

submit accepts findings.json: {episode_id, findings:[{type, affected_ids, claimed_amount_minor, currency,
evidence_ids, explanation}]}. explanation is a short justification.

- Limits: max 30 findings, 10 evidence IDs and 1,000 characters of explanation per finding.
- Invalid structure ends the episode with reward −1 and an error in the grader log.
- Matching is one-to-one with the answer key. TP requires the correct type, canonical affected_ids, an
  amount within the stated tolerance, the currency, and at least one complete acceptable evidence set.
  Unmatched and repeated findings are FP; missed reference errors are FN.
- The generator must provide available records sufficient to verify each finding.
- Publish the normalization code, tolerance rules, and the tie-breaking rule for ambiguous matches.
- P=TP/(TP+FP), R=TP/(TP+FN), F1=2TP/(2TP+FP+FN). Zero denominator → 0. Empty key and empty findings →
  F1=1; empty key with findings → F1=0.

Terminal reward = clip(2·F1 − 1 − 0.002·inspection_steps, −1, 1). Episode return equals this reward. An
experimental reward may be added but the common one must be kept and reported separately.

Tests must show: a complete correct answer with evidence beats silence on erroneous ledgers; silence beats
false accusations on clean ledgers; duplicates gain nothing; flagging every row/type scores poorly; saving
steps only slightly separates equally correct answers. Check guessed IDs, unsupported evidence, currencies,
resubmission, invalid input, and timeouts.

## 06 Closed evaluation

The jury checks correctness of data and grader, not team agent reward. Open train/dev configurations and
seeds are separate from closed seeds, new parameter combinations, and harmless transformations. Organizer
policies: random explorer (fixed seed), simple reconciliation algorithm, "flag everything" attack, oracle
(grader-only). All four run on the same 20 hidden episodes (five clean, five with interacting errors).
Another 20 paired checks change order and IDs.

## 07 Minimum requirements

Generator (4 error types, 2 interacting scenarios, clean companies, distractors); environment with
reset/step, section-04 actions and a 100-step limit; shared matcher and terminal reward with attack tests;
recorded trajectories without the closed answer key; official check without network, paid APIs, or GPU;
container instructions and a single check command. Offline limits: Python 3.11, 2 CPU, 4 GB RAM, no GPU,
1 GB per solution, 60 s per episode, 100 steps.

## 09 Submission

Licensed source with generator, environment, pinned dependencies; README with container instructions and a
single check command; matcher and reward code, schemas, policies; 10 open train and 10 dev episodes; tests;
four baseline policy adapters; trajectories.jsonl (episode_id, step, action, observation, reward, terminated,
truncated); design note; demo (scripted policy is enough).

## 10 Evaluation criteria (100 points)

| Criterion | Points | What is assessed |
|---|---|---|
| Contract and isolation | 25 | 20 fixed checks of reset/step, schemas, limits, termination, invalid input, absence of leaks |
| Data and answer key | 25 | 20 closed episodes: accounting equalities before injection, declared discrepancy after, independent sufficiency of evidence |
| Reward reliability | 25 | 20 checks of matching, clean cases, FP, duplicates, cost, attacking answers |
| Reproducibility and generalization | 15 | 20 paired checks: exact repetition; permutation or ID changes preserve oracle answer and reward |
| Engineering and explanation | 10 | single-command run, configuration versions, trajectory logs, measured failure analysis, honest limitations |

Leaking closed data, writing to the grader, real financial data, or a non-working core blocks evaluation.
Show P, R, F1, return, steps, and agent time as diagnostics. A beautiful UI earns no points.

## Team ideas table (from the organizers' idea list)

1. Paired episodes with opposite answers (legit repeat vs duplicate; time zone change flips the period).
2. Independent reconciliation of the answer key (separate checker recomputes from public records + policy).
3. Difficulty through an action budget (20/50/100 steps, ledger sizes, reachability of evidence).
4. Trajectory diagnostics (first step when complete evidence seen; classify misses: search, amount, evidence).
5. Dev with new regimes (held-out parameter combinations; split source histories before variants).
6. Two paths to one piece of evidence (two complete acceptable evidence sets).
7. Format and boundary checks (UTC vs local offset; currency exponents; boundary rounding).
8. Share of fully closed episodes (all errors found with evidence, no FP).
9. Verifiable partial credit on train (experimental reward, compared against baseline).
10. LLM-as-judge for explanations (optional).

Suggested split: train 10 = 2 clean, 4 single (one per type), 2 linked, 2 boundary; dev 10 = 2 clean with
plausible repeats, 4 single with new parameters, 2 linked under new conditions, 2 larger ledgers.
