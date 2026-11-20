# auditgym design note

auditgym is a reproducible environment for training and evaluating financial-audit agents. One episode is
one synthetic company and one reporting period. The agent reads records through five tools, then submits
findings with evidence. A grader in another process scores them against an answer key that the generator
derived from a recorded causal change. Everything runs offline on the Python 3.11 standard library.

This note describes the current code (version 0.2.0). The historical day-1 plan is in [PLAN.md](PLAN.md).

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
  -> answer key from the erroneous books; provenance = exact record diff clean -> erroneous,
     with the clean-records digest and the final public digest
  -> independent verification (verify.py); a failing candidate is resampled from a derived seed
```

Errors are booking overrides on an error-free history (a wrong rate, a wrong posting timestamp, an allocation
cap, a second posting of the same invoice). The engine re-posts everything, so cascades stay consistent: a
receipt for an invoice booked at a wrong rate relieves the booked carrying amount and its FX difference follows.

Custom PRNG (SplitMix64, integer arithmetic only) instead of `random`, `Decimal` for money and rates, no set
iteration, LF-only UTF-8 writers. Same seed, config and version give byte-identical files. This is verified on
Windows 10 with Python 3.11.4 locally, and in CI on ubuntu, macOS and Windows (Python 3.11) and inside the
container (section 13).

## 2. Data contract

| File | Content |
|---|---|
| `public/manifest.json` | schema_version, generator_version, episode_id, company (synthetic), base_currency, currency_exponents, period_start/end, ledger_extract_end, timezone, record and document counts, rounding |
| `public/ledger.csv` | exactly `row_id,timestamp,account,debit_minor,credit_minor,currency,entity_id,invoice_id,payment_id`; empty field = null; base currency; one positive side |
| `public/invoices.jsonl` | doc_id, invoice_id, kind (sales/purchase), entity_id, issued_at, due_at, currency, total_minor, line_items[{line_no, description, quantity, unit_price_minor, amount_minor, ref}] |
| `public/payments.jsonl` | doc_id, payment_id, kind (receipt/disbursement/refund), entity_id or null, timestamp, currency, amount_minor, invoice_refs or null, bank_ref |
| `public/fx.csv` | date, source_currency, target_currency, rate (decimal string, 1 source = rate target); record ID `YYYY-MM-DD:SRC:TGT` |
| `public/policy.json` | UTC-offset schedule of the company time zone, period rule, FX date rule and publication calendar (holidays), conversion and rounding, posting/allocation/refund rules, journal grouping, duplicate rule (two issued_at values are duplicates when they denote the same instant, whatever offset each is written with), chart of accounts |
| `grader/truth.json` | issues (issue_id, type, variant, scenario, affected_ids, expected_amount_minor, currency, tolerance_minor, evidence_sets, explanation) and the doc-ID alias table |
| `grader/provenance.json` | seed, configs (sorted keys), attempt, history summary, injections with their semantic change, distractors, record-level ops (`add`/`remove`/`set` with before/after), `clean_digest`, `clean_records_digest` (order-independent hash of the reverted clean tables), `final_digest`, rejected attempts |

Times are ISO-8601 with an offset; the same instant may be written in UTC, company time or another offset
(`ts_repr`). Local dates always come from the policy's offset schedule. Money is integer minor units with the
currency exponent (JPY and KRW 0, KWD and BHD 3, others 2). The ledger extract covers the reporting period plus a
7-day cut-off window, with opening journals for items open at period start. IDs are opaque random tokens, unique
across tables, never sequential, and assigned the same way for injected and ordinary records.

## 3. Errors, variants, scenarios, distractors

| Type | Variants | Canonical affected_ids | Amount (base minor units) | Acceptable evidence sets |
|---|---|---|---|---|
| duplicate_invoice | same-day copy with identical line refs | both invoice_ids | one copy's posted amount | {doc A, doc B, payable row A, payable row B} or {doc A, doc B, expense row A, expense row B} |
| unallocated_payment | missing, partial | payment_id + invoice_id | amount wrongly credited to 2900 | {payment doc, invoice doc, 2900 row} |
| wrong_fx_rate | utc_date, posting_date, stale_rate, transposed | invoice_id or payment_id | abs(posted - policy amount) | {doc, primary row, fx row of the correct date} or {doc, counter row, fx row} (invoices) |
| wrong_period | booked_early, booked_late, utc_wall_clock | invoice_id or payment_id | posted primary amount | {doc, primary row} or {doc, counter row} (invoices); {doc, bank row} (payments) |

Interacting scenarios:
- `boundary_fx_payment`: a partial foreign-currency receipt is booked by its UTC date and UTC wall clock:
  wrong period and wrong FX rate on the same payment, one root cause. The receipt is placed just after local
  midnight at the period boundary (positive UTC offsets) or shortly before the period's last midnight (negative
  offsets). It needs weekdays on both sides of the period end.
- `fx_invoice_partial_allocation`: a foreign invoice booked at a wrong rate, then its receipt partly left in 2900.
  The scenario always uses the `partial` variant of the unallocated receipt (part relieved against the invoice,
  part left in 2900), so the receipt's 1100 relief and 7900 difference follow the invoice's wrong carrying amount.
  A configuration whose `unallocated_payment` variants exclude `partial` is a ConfigError.

Distractors (correct by policy): same supplier, amount and date with different line refs; recurring monthly
amounts (subscription refs are unique per supplier and month; the only repeated reference in the committed episodes is
the injected duplicate in d03); split payments; one receipt for two invoices;
underpayments; overpayment plus refund; receipts without invoice reference (always at least one, so a 2900 credit
is never a tell by itself); documents minutes before or after local midnight at the boundary, for invoices and
payments (`boundary_doc`, `midnight_fx`); weekend and holiday FX; near-midnight foreign documents converted on their
local date. Default distractor counts per size are fixed in `auditgym/config.py` (`DEFAULT_DISTRACTORS`: midnight_fx 2/3/4 for
small/medium/large), and `boundary_doc` is drawn from a range per size (`DEFAULT_DISTRACTOR_RANGES` in the same file:
2–7, 3–8 and 4–8). A twin option (`"twin": true`) rebuilds the same history with the
duplicate turned into a legitimate repeat: same ledger, opposite answer (train t03/t10). The twin keeps the whole
history for every seed.

Data realism (the shortcut audit and its fixes): target documents are ordinary draws. Quantities and unit prices
stay inside the catalogue ranges (no scaling), and ordinary invoices also clear the size floors used for targets.
Ordinary invoices and payments fall outside business hours, and some ordinary documents and non-FX targets fall on
weekends. Correctly booked receipts, disbursements and invoices are placed at the period boundary and near local
midnight in the same windows as the boundary errors. Duplicates and legitimate repeats share the same terms
(14/30/45 days) and payment-status distribution. Clean ledgers never overdraw the bank.
FX targets still never fall on a weekend or an FX holiday, because a same-day rate is required.
`python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells` measures 36 document rules and 5
episode-level rules on 1000 generated episodes (750 with errors; 3799 of 141 479 documents affected, a base rate of
0.027) and writes `runs/tells/summary.md` and `summary.json`, byte-identical across runs (about 160 s). The best
document rules are about eight times the base rate and look for twin invoices ("paid twin invoice": precision 0.231 at
recall 0.079; "invoice with a twin": 0.218 at recall 0.291): a twin is where a duplicate must be looked for, and about
four in five twin invoices are not in the answer key. The episode rules that fire stay within 0.03 of their base rate (0.753 and
0.770 against 0.750). The largest foreign purchase is the FX target in 17 of 180 eligible episodes (0.094, chance
0.103). `tests/test_tells.py` asserts the same thresholds on the 20 committed episodes (33 document rules, 5 episode
rules); on 100 generated episodes it asserts the window-by-kind and window-count rules, which the CLI does not measure,
and it smoke-runs the CLI over the 36 rule names.

Guards: injected monetary differences are at least 100 minor units (50 times the tolerance); FX targets fall
on dates with a published rate; unallocated targets are single-reference receipts with no other receipt on the
invoice and no legitimate excess; (type, affected_ids) is unique per episode; at most 12 errors per episode
(`MAX_ERRORS`). Unallocated receipts carry an evidence assumption: see section 10.

## 4. Environment contract

`reset(seed, config, options)` returns `(observation, info)`. The config is a generator config,
`{"episode_dir": path}`, or either plus `"transform"`; `options={"config": ...}` is used when no config is given,
and other option keys are ignored. The first observation holds `task`, `manifest`, the full `policy`, and
`remaining_steps`. `step(action)` returns `(observation, reward, terminated, truncated, info)`.

| Action | Arguments | Result |
|---|---|---|
| list_records | table (ledger/invoices/payments/fx), cursor (null or next_cursor), limit 1..50 | rows, next_cursor, total |
| get_record | table, id | record |
| get_document | doc_id | invoice or payment document |
| calculator | expression (+ - * / parentheses, decimals; no names, no exponent; at most 256 characters and 200 tokens) | value (decimal string) |
| submit | findings.json | accepted, findings_received |

Actions may also be written as `{"action": ..., "args": {...}}`. The alias is accepted by the schema and the
environment alike (`schemas/action.schema.json` has both forms). Observations hold only `result`, `error`, and
`remaining_steps`. Errors are `{code, message}` with messages of at most 200 characters and input echoes cut at 64
characters; unexpected exceptions become `internal_error` without a traceback. Every call consumes a step, errors
included.

Structural errors (`bad_args`, `unknown_action`, `unknown_table`, `invalid_submission`) are exactly the cases the
schema rejects; semantic outcomes (`unknown_id`, `bad_cursor`, `calc_error`, a submission with another episode's
ID) are not schema errors. `calc_error` covers more than 200 tokens, nesting deeper than 32, division by zero,
out-of-range results and empty or malformed expressions; a non-string or longer-than-256-character expression is
`bad_args`.

Submission limits (published in the task as `limits`): at most 30 findings, 10 evidence IDs, and 1,000 explanation
characters per finding. Every ID must be a non-blank string of at most `max_id_chars` (64) characters. An ID that
breaks this rule makes the whole submission invalid (reward −1), including an extra evidence ID; well-formed unknown
extra IDs are ignored. `claimed_amount_minor` must be an integer; an integral float such as `106965.0` is coerced to an
integer by the environment and by the `grade` command alike.

100 steps including the submit; step 100 without a submit, or the time limit (`time_limit_s` in the task, 60 s by
default), truncates with an empty answer. Calls after the end return `episode_finished` and change nothing. In
`train` mode the terminal reward and TP/FP/FN are returned at the end; in `eval` mode the policy always gets 0.0 and
the grader keeps everything. Resubmission is ignored.

## 5. Isolation and leaks

The host process holds the episode, the answer key and the grader. The policy runs as `python -m auditgym.agent`
in a child process. The child gets:

- an empty temporary working directory;
- a minimal environment: no seed, no secret, no episode or grader path;
- an import path that holds a staged copy of the agent-side modules only (`STAGED_MODULES` in `protocol.py`), plus
  the repository's `examples/` policies. The oracle, grader, generator and episode code are not importable there.
  Compiled files are not staged, because bytecode carries the absolute source path;
- JSON lines over stdio, with observations as the only input.

The channel is bounded in every direction (constants in `protocol.py`):

- a line over `MAX_LINE` (2,000,000 bytes) is discarded up to the next newline and counts as malformed;
- at most `QUEUE_LINES` (4) raw lines wait in the host;
- stderr keeps a tail of `STDERR_TAIL` (2,000 bytes);
- writes go through a thread with a `WRITE_TIMEOUT_S` (10 s) deadline, so an agent that stops reading cannot stall
  the host past the time limit;
- an action line deeper than `MAX_DEPTH` (32), with more than `MAX_NODES` (100,000) JSON nodes, a number longer than
  `MAX_NUMBER_CHARS` (40) characters, or a non-submit line over `MAX_NONSUBMIT_CHARS` (2,048) is answered with
  `unknown_action` and costs a step; the trajectory stores `{"invalid_action": <first 256 characters>}`;
- any other JSON value as the action, null included, goes to `env.step()`, which returns a bounded error;
- a stray `print()` goes to stderr and cannot desynchronise the protocol;
- a child that exits, crashes, or cannot be written to is an agent error: the episode is graded as an invalid
  submission (reward −1, `closed` false, status `agent_exited`), never as an empty answer, and `run` exits 3.
  Only the time limit and the step limit give empty answers.

The host hashes every file under `auditgym/` (bytecode included), `configs/*.json` and `schemas/*.json` before and
after each agent run. A change is an agent error (`agent_error`), and changed bytecode is deleted. The processes the
host tracks are killed when the run ends (process group on POSIX, Job Object on Windows). This detects tampering; it
does not prevent it.

Noninterference is tested by replay (`tests/test_noninterference.py`): five policies, in process and in the child,
on episodes whose answer key is shuffled, replaced by another episode's, or emptied. The agent's observations,
rewards and info are byte-identical (eval mode at every step; train mode up to the terminal step). Timing is not
covered, because the time limit is part of the contract. `tests/test_redteam.py` and `python -m auditgym.redteam`
probe hostile behaviour: 256 MB without a newline, 256 MB on stderr, two million short lines, an agent that stops
reading stdin, a flood of invalid UTF-8 that the agent never reads (host peak under the limit), and a grandchild
process that must die with the agent.

Limits: a child running as the same OS user is not a sandbox. Outside a container it can read files whose path it can
guess, and its parent's command line (measured on Windows). It can also read the host's environment, where
`--secret-env` values live: on Windows from the parent's process memory (`python -m auditgym.redteam --parent` starts a
policy through the harness and it finds a host variable there; measured locally), on Linux through
`/proc/<ppid>/environ` (expected, not measured outside the image). Inside the image the separate policy uid blocks
this (below); the `--user 10001` and `--cap-drop ALL` fallbacks do not. A process that leaves the
tracked group or job (for example with `setsid`) survives the run. Only a container or a separate OS user contains
that. The policy-adapter path (`module:Class`) follows the same rules: any class with `act(observation, reward, info)`
runs as `module.path:ClassName` (`--policy-path DIR` for code outside the repository); names are validated before a
run starts, and the oracle is refused in the child (`examples/custom_policy.py`, `examples/hostile/`).

Container (P9): the environment and grader run as root; every policy child runs as uid 10002 (`agent`, no
supplementary groups, umask 077) in a temporary directory it owns, started with `Popen(user=, group=, extra_groups=[],
umask=)`; `close()` kills every process of that uid. `/app` is 0750 root:auditor and `/app/runs` 0770, so the agent can
neither read the package, seeds files or grader outputs nor write to the code; the host's environment is protected by
the different uid (other-uid `/proc/<pid>/environ` needs CAP_SYS_PTRACE). `tests/test_container.py` runs inside the image
in CI and must not skip; `--user 10001` and `--cap-drop ALL` fall back to a same-user child with one warning and still
pass. Only `PermissionError` falls back; any other start failure is an agent error, so the fallback cannot hide a fault.
Once a switch has worked in a process, a refused `chown` or `setuid` is an error, never a silent start as root; a host
whose `/proc` cannot be listed never switches, because `kill_uid` could not see the agent's processes.

Strict mode (opt-in): with `AUDITGYM_REQUIRE_AGENT_USER=1` the fallback is an error (`AgentUserRequired`, not an
`OSError`, so it is never graded as an agent error). `check`, `run` (when it starts a child), `demo`, `viewer` and
`budget` start and stop one policy child first and exit 2 with one `error:` line before the first episode and before
any report. The image does not set it: a runner that adds `--user` or drops capabilities must still pass. CI runs the
check and the container tests in strict mode in the default image (none skipped), and checks that strict mode with
`--cap-drop ALL` exits 2 with exactly one line.

## 6. Matcher and reward

Normalization (`auditgym/matcher.py`): exact type; affected and evidence IDs trimmed, deduplicated, compared
as sets (case-sensitive); a document may be cited by doc_id or by invoice_id/payment_id (alias table);
currency upper-cased; amount within `tolerance_minor` = 2; a finding is supported when one acceptable
evidence set is a subset of its evidence IDs (extra IDs ignored). Matching is a one-to-one maximum matching
(Kuhn's algorithm); tie-break: findings in submission order, issues in issue_id
order. Unmatched and repeated findings are FP, unmatched issues FN. P, R and F1 follow the case definitions,
including F1 = 1 for an empty answer on a clean episode.

Reward (`auditgym/reward.py`), computed with exact fractions: `clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)`,
where inspection_steps counts every step except the submit. Invalid structure gives −1.

Experimental soft reward (`auditgym/reward.py`, reported in `grades.jsonl`, in the summary tables and in their own
columns; it never replaces the common reward): per issue, 0.5 for the right type and IDs, +0.25 for amount and
currency, +0.25 for a complete evidence set. The credit is assigned one-to-one by maximum total weight (a Hungarian
assignment on a padded square matrix), so the order of the findings cannot lower an exact answer. softF1 =
2S / (n_findings + n_issues), so spam lowers it. Before this change a greedy assignment could score an exact answer
below 1 when two issues shared a type and IDs; generated episodes never have such keys, because `inject.py` rejects
them, but a hand-made key could.

Diagnostics (`auditgym/diagnostics.py`; micro and macro figures, miss reasons and FP causes are printed in `summary.md`
and `report.md`; the unobserved-citation list is written to `grades.jsonl` only): micro precision and recall (ΣTP over
Σ(TP+FP) and ΣTP over Σ(TP+FN)), macro P and R (means over episodes, where a clean episode contributes 0 even for a
correct empty answer), the first step at which all evidence for each error was observed, miss reasons per issue
(`amount`, `evidence`, `search`, `not_flagged`), false-positive causes (the distractor kind a finding touches, else
`near_issue`, else `unrelated`), and the unobserved-citation alarm (IDs a finding cites that never appeared in an
observation; the oracle scores 1.0 by construction, so a non-zero value for a policy is evidence of a guess or a leak). A zero alarm does not prove there is no leak: an
agent that holds leaked IDs can fetch each one with `get_record` or `get_document`, after which it counts as observed, and
made-up IDs that exist nowhere count as unobserved, like leaked ones.

## 7. Verification of data and answer key

`python -m auditgym verify DIR` runs the named checks below on an episode directory. Generation runs the same
checks against the clean twin before an episode is returned. The directory mode of `provenance_roundtrip` checks
the stored digests instead of the twin.

| Check | What it proves |
|---|---|
| records_schema, ids_unique | published fields and types; IDs unique across tables |
| clean_equalities | clean books rebuilt from provenance: every journal and the trial balance balance; the independent auditor finds no discrepancy and no anomaly |
| provenance_roundtrip | revert-and-reapply reproduces the published tables; the reverted tables hash to `clean_records_digest`; `public_digest()` equals `final_digest`; every declared issue has an op that touches its records. At generation time the reverted tables are also compared with the clean twin |
| declared_discrepancies | the independent auditor (`auditor.py`, which imports only the standard library and `timeutil`: no generator module and not `money.py`; its FX conversion and proportional relief are its own integer arithmetic, tested against `money.py` on 10 000 random cases each in `tests/test_verify.py`) reproduces exactly the answer key: types, IDs, amounts, evidence sets |
| evidence_sufficient | the separate evidence checker (`evidence_check.py`) re-derives type, IDs and amount from each evidence set alone, plus policy and manifest; dropping any record from a set breaks it (test). For `unallocated_payment` the set cannot show that no other receipt settled the invoice; that rests on a generator guarantee (section 10) |
| budget_feasible | reading every page of every table plus the submit fits in 100 steps |
| no_surface_tells | every injected or modified row has an untouched row with the same account and null pattern; in directory mode it fails when issues are declared but no ledger op exists |
| no_leaks | no answer-key markers or seed in public files |

`evidence_check.py` imports nothing from `auditor.py` or `money.py`. It reads UTC offsets from
`policy.utc_offset_schedule`, uses a fixed duplicate-signature field list, derives nothing unless
`policy.duplicate_rule` names each field, and converts with `fractions.Fraction`. It shares only the ISO timestamp
parser and the `Episode` container. `tests/test_verify.py` cross-checks its conversion against `money.convert_minor`
on seeded random cases.

The digests are tamper evidence against accidental or casual edits, not a signature: someone who edits the ops and
recomputes the digests passes. `clean_digest` (the public digest of the clean twin) cannot be recomputed without the
twin's row order.

## 8. Reproducibility and paired checks

`transform.py` permutes rows, remaps every ID consistently in records, answer key and provenance, rewrites
timestamps as the same instants in another offset, and (`rename_seed`) replaces the company name and every invoice line
description with synthetic wording from a seeded injective mapping, in records and provenance, keeping reference tokens
such as `SUB-2025-05-6014`. Counterparties appear in the public records only as entity IDs, which the remap replaces. Issue numbering, affected-ID order and evidence order follow
content roles, not ID strings, so the oracle answer maps one to one.

The official check (`python -m auditgym check`) groups its named checks in the five rubric groups of `RUBRIC` in
`auditgym/check.py`. The section keys in `runs/check/report.json` are stable; the grouping is presentation only.
Sections:

- `F_contract`: 20 named contract checks in process on one hidden-like episode (`contract_battery.py`): reset and
  observation keys, 50-row pages, record keys in order, the same cursor twice and again after a fresh reset, unknown ID
  and action, calculator limits, submit and finished episodes, truncation at step 100 and not before, a frozen-clock
  time limit, eval hiding the reward, -1 for invalid and foreign submissions, the observation schema, and a 300-action
  seeded fuzz with a reset at every episode end. Every group runs inside `try`, so a crash is a failed row.
- `E_leaks`: the observations of this run's hidden-like baselines (2219) hold only the allowed fields and no
  answer-key marker; oracle trajectories are never published.
- `B_committed_episodes`: each committed episode regenerates byte for byte from its seed and config and verifies.
- `B_replay`: recorded actions from `runs/train_dev/trajectories.jsonl`, for each split and policy (10 groups, the
  silent baseline included), replay in a fresh environment with JSON-equal observations and the same terminal reward.
- `C_data`: the hidden-like episodes verify; resampling rates are measured.
- `C_reward`: reward properties on every episode. On every error episode an attack battery runs: a type shotgun
  (one finding under each type), an amount ladder (neighbouring amounts), junk padding (the reward equals
  `clip(2F1 − 1)` exactly and stays below the answer alone), evidence stuffing (a true positive, by the published
  rule) and a right amount with the ID of an unrelated real invoice (not a true positive). Every distractor in the
  grader's provenance also becomes the most plausible false finding, built from the real records by the published
  rules: base currency, the posted base amount of the key row, the documents and rows the rules require, and for FX the
  neighbouring published date's rate. On an error episode it costs exactly one false positive when added to the oracle
  answer and matches no issue alone (an accusation that names only the records of an injected error is left out,
  and the line is SKIP only when every accusation of that kind is left out); on a clean episode it
  scores −1, below silence. Each such accusation must also match a decoy key that states exactly its claim and no
  decoy that differs in one criterion (type, IDs, currency, amount beyond tolerance, evidence), so a matcher that
  ignores any one criterion fails. `tests/test_check_battery.py` shows that the same constructors give true positives
  on the records of real issues. The baselines include `silent` (submits nothing at once); the check asserts
  auditor > silent.
- `D_paired`: same seed and config regenerate identical records and answer key; the same actions reproduce identical
  transitions (random explorer); isolated child and in-process runs agree; transforms (permutation, remap, timestamp
  representation, renaming) keep the oracle answer and reward, and the auditor matches the same (issue, amount) pairs
  (93 checks).
- `A_unit_tests`: the whole unit suite (`unittest discover`), reported as one check with run, passed and skipped
  counts.

The report header states the coverage (615 named checks of 78 kinds; a kind is one property, and most run on every
episode they apply to) and whether the policy child ran as a separate user.

Unit tests rerun generation under two `PYTHONHASHSEED` values (`tests/test_generator.py`), and the committed schema
files must stay byte-equal to the generated ones (`tests/test_contract_fuzz.py`, test_committed_schema_files_equal_generated_ones).

Closed runs: `python -m auditgym check --seeds-file FILE --secret-env VAR --out DIR` runs sections C, D, E and F and
the replay of its own runs on the organizer's episodes, and warns about seeds of 40 bits or fewer when no secret is
set. Checks that need error or clean episodes missing from the file are
reported as SKIP. It writes `runs/check_closed` by default, never `runs/check`.

## 9. Measured results

Numbers are copied from generated files. The full tables are in [README.md](../README.md#evaluation) (and
[README.ru.md](../README.ru.md)); the sources are `runs/check/report.md` (hidden-like set),
`runs/train_dev/summary.md` (open splits), `runs/budget/summary.md` and `runs/stress/report.md`.

Hidden-like set (20 episodes from the public master string `auditgym-check-v1`, eval mode, isolated agents):

| Policy | Return | F1 | Micro P | Micro R | Steps | Closed share | FP on clean |
|---|---|---|---|---|---|---|---|
| oracle (grader-side) | 1.000 | 1.000 | 1.00 | 1.00 | 0.0 | 1.00 | 0 |
| scripted auditor (verifier code) | 0.936 | 1.000 | 1.00 | 1.00 | 32.0 | 1.00 | 0 |
| recon (simple reconciliation) | −0.589 | 0.231 | 0.16 | 0.75 | 32.0 | 0.00 | 40 |
| silent (submits nothing at once) | −0.500 | 0.250 | n/a | 0.00 | 0.0 | 0.25 | 0 |

The empty answer scores −0.500: +1 on the 5 clean episodes and −1 on the 15 error episodes. Recon and the random
explorer score below it; only the scripted auditor and the oracle beat it.

Recon's misses on this set are all `not_flagged`: its recall is 0.6 on FX and 0.625 on period errors, and it is 1.0 on
duplicates and unallocated receipts. Recon's return fell after the data shortcuts were removed (commit `a94d9b9`,
parent `bb80adb`): dev −0.545 → −0.689 and train −0.638 → −0.690 (`git show a94d9b9^:runs/train_dev/summary.md`
against the current file), and the hidden-like set −0.490 → −0.589 (`git show bb80adb:runs/check/report.md`). The
scripted auditor barely moved (dev 0.947 → 0.943). The cause has not been isolated; the same change also altered the
distractor mix.

Open splits: scripted auditor return 0.971 (train) and 0.943 (dev); recon −0.690 and −0.689; silent −0.400 and
−0.600. On dev, recon misses are
`not_flagged` (FX recall 0.22, period recall 0.25). Macro P and R count clean episodes as 0, so the oracle sits at 0.7
(train) and 0.8 (dev); micro P and R are the figures to read.

Action budget (dev, scripted auditor and recon; `python -m auditgym budget`): auditor F1 0.472 at 20 steps, 1.000 at 50
and 100; recon F1 0.082, 0.178 and 0.178.

Generator stress (`python -m auditgym stress --n 300`): 300 random configurations, 282 generated and verified, 18
infeasible with a ConfigError (17 `boundary_fx_payment` with a fixed period, 1 `UTC` request needing an offset), no
verify failures; 17 extreme configurations all verified, and the scripted auditor closes all of them in 11 to 47 steps.
Timings and memory are machine-dependent, counts are not.

Feasibility: an unspecified time zone or period is redrawn (on a side RNG stream, so feasible draws and the committed
episodes are unchanged) until the requested errors can be placed. A fixed period with `boundary_fx_payment` fails when
the period's last day or the next day is a weekend: 17 of the 36 months of 2025–2027 are infeasible, and the
ConfigError names the nearest feasible months. The count follows from the rule (the period's last day and the first day
after it must both be weekdays): `python -c "from auditgym.config import feasibility_problems as f; print(sum(bool(f('UTC', f'{y}-{m:02d}', {'boundary_offset': False, 'boundary_weekdays': True, 'utc_date': False})) for y in (2025, 2026, 2027) for m in range(1, 13)))"` prints 17. A fixed zero-offset time zone fails for offset-dependent requests. Both
give a one-line ConfigError. The generator never silently injects fewer errors than requested. `check` fails if
resampling exceeds half the number of episodes in the check set.

## 10. Limitations

Also listed in [README.md](../README.md#limitations) and mirrored in [README.ru.md](../README.ru.md).

- **Platforms.** Local runs: Windows 10, Python 3.11.4. CI: ubuntu, macOS and Windows with Python 3.11 (the Windows
  runner set up CPython 3.11.9), and the container. Python 3.12 and 3.13 were not tested. The POSIX process-tree branch
  runs in CI, not locally.
- **Container.** Built and run in CI with `--network none --cpus 2 --memory 4g --pids-limit 512`. Inside the image
  the host runs as root and every policy child as uid 10002 (`agent`, section 5). Under `--user 10001` or
  `--cap-drop ALL` the policy falls back to the host's user with one warning line; a same-user child can then read
  the host's environment, where `--secret-env` values live (measured on Windows outside a container; expected on
  Linux).
- **Isolation** is a process boundary, not a sandbox (section 5). Open train and dev answer keys sit in the repository
  by design, so a child running as the same OS user can read them.
- **Seeds.** The generator is open source. With no host secret and a guessed config, a small seed can be recovered from
  the manifest's `episode_id` (`episode_id = sha256(seed | config | secret)`), and the answer key can then be
  regenerated. Use 63-bit seeds and `--secret-env`. `run` warns about seeds of 40 bits or fewer when no secret is set. Public records allow brute-forcing small seeds in any case.
- **Hidden-like set.** It comes from a public master string. It tests the pipeline, not secrecy; closed evaluation
  uses `check --seeds-file`.
- **Scripted auditor.** It shares `auditor.py` with the verifier. Its perfect F1 shows that every scenario is solvable
  through the tool interface within the budget, not that an agent would reason this way.
- **Unallocated payment evidence.** The three-record evidence set relies on a generator guarantee: the receipt references
  a single invoice, and no other receipt is booked against that invoice. The cited records cannot show this; an agent can
  confirm it only by reading all payments.
- **Shortcut tells** are measured only for the rules written down in `auditgym/tells.py` (section 3). A feature nobody
  listed may still leak.
- **Evidence padding.** Extra evidence IDs up to the 10-ID cap are free (published superset rule); the battery checks
  that padding stays a true positive and does not penalize it.
- **Paired transforms** cover row order, ID remap, timestamp representation and renaming. There is no date shift:
  period boundaries, FX dates and time-zone rules would have to move together.
- **Accounting model.** Deliberately small: base-currency ledger, payments in the invoice currency, no taxes, credit
  notes or cross-currency settlement, eleven built-in time zones instead of the IANA database.
- **flag_all** is a format-level attack. Smarter attacks are covered by the reward battery in `check` (section 8).
- **Evidence IDs and amounts.** A blank or over-long ID (more than 64 characters) makes the submission invalid, even as
  an extra evidence ID. Both are kept in this version: the task publishes `max_id_chars` and also says unknown extra IDs
  are ignored. An
  integral float `claimed_amount_minor` (`106965.0`) is coerced to an integer by both the environment and `grade`.
- **Explanations are not graded**; the reward depends on fields and evidence only. A judge for explanations is not
  implemented. Time-zone twin pairs for period errors are not implemented; only the duplicate twin pair t03/t10 exists.
- **Experimental reward.** It is reported next to the common reward and never replaces it.
- **No model was trained**, so no improvement is claimed.

## 11. Case requirements and where they are tested

| Requirement (case section 05) | Test or check |
|---|---|
| correct answer with evidence beats silence on erroneous ledgers | `tests/test_reward.py` RewardPropertyTests; check `C_reward` (live episodes) |
| silence beats false accusations on clean ledgers | `test_reward.py`; `tests/test_env.py` test_empty_answer_on_clean_episode_is_rewarded; check `C_reward` (one accusation per distractor, built from the real records; one check line per kind) |
| duplicates gain nothing | `test_reward.py` test_duplicates_gain_nothing; `tests/test_matcher.py` test_repeated_finding_is_false_positive |
| flagging every row or type scores poorly | `test_reward.py` test_flag_everything_scores_poorly; check `C_reward`: flag_all mean return <= -0.9 |
| saving steps only slightly separates equal answers | `test_reward.py` test_saving_steps_only_slightly_separates_equal_answers; check `C_reward` |
| guessed IDs | `tests/test_matcher.py` test_guessed_ids_score_nothing; check `C_reward` mutants |
| unsupported evidence | `tests/test_matcher.py` test_incomplete_evidence_is_false_positive; `tests/test_generator.py` test_removing_a_decisive_record_breaks_the_evidence |
| currencies | `tests/test_matcher.py` test_wrong_currency_is_false_positive |
| resubmission | `tests/test_env.py` test_resubmission_is_ignored |
| invalid input | `tests/test_matcher.py` test_invalid_structures; `tests/test_env.py` test_invalid_submission_ends_with_minus_one, test_errors_are_bounded_and_consume_a_step; `tests/test_calculator.py`; `tests/test_contract_fuzz.py` |
| timeouts | `tests/test_env.py` test_time_limit_truncates, test_step_limit_truncates_with_empty_answer; `tests/test_isolation.py` test_agent_that_stalls_is_truncated |
| hostile policy processes | `tests/test_redteam.py`; `tests/test_noninterference.py`; `python -m auditgym.redteam` |
| shortcut tells | `python -m auditgym.tells` ([runs/tells/summary.md](../runs/tells/summary.md)); `tests/test_tells.py` |
| contract: reset/step, schemas, limits, termination, invalid input, leaks | check `F_contract` (20 named checks) and `E_leaks`; `tests/test_contract_battery.py`, `tests/test_contract_fuzz.py` |
| attacking answers | check `C_reward` battery with decoy keys; `tests/test_check_battery.py` |

## 12. Viewer

`python -m auditgym viewer` writes one offline HTML file for people, never for agents: no CDN, system fonts,
the graph engine inlined. It shows the policy benchmark, every open episode (the answer key labelled as the
grader view, ledger, documents, FX rates, policy), every run (the trajectory with the step at which all evidence
for an error was first seen, and the verdict with tick marks for matched, unmatched and missed) and an
Obsidian-style force graph of documents, ledger rows, FX rates, entities and accounts, with red rings on the
evidence of each error. English and Russian, dark and light. The visual pass followed the unslop skill by Damir
Sokolovsky (GitHub [@heydamir](https://github.com/heydamir/unslop), CC-BY-4.0): one neutral ink ramp, one cobalt accent, no
gradients or glows in the interface chrome, and the graph as the one rich element. The static design mocks in
`docs/design/` are not rebuilt from the current data.

## 13. Continuous integration

Workflow `.github/workflows/check.yml`, triggered on push, pull request and manual dispatch:

- Job `check` on `ubuntu-latest`, `windows-latest` and `macos-latest` with Python 3.11, `PYTHONHASHSEED=0`:
  `python -m auditgym check`; then `build-splits` and `schemas`, followed by `git diff --exit-code` on `episodes` and
  `schemas`; then a replay of the open splits, followed by `git diff` on `runs/train_dev/trajectories.jsonl`. The
  check report is uploaded as an artifact.
- Job `docker` on `ubuntu-latest`: `docker build -t auditgym .` (base `python:3.11.10-slim-bookworm`), `docker image ls`,
  then `time docker run --network none --cpus 2 --memory 4g --pids-limit 512 auditgym` (the container is kept so that
  `runs/check/unittest.log` and `report.md` can be copied out, printed on failure and uploaded); then
  `tests.test_container` and `tests.test_redteam` inside the image, failing if any container test is skipped; then the
  check and `tests.test_container` again with `--user 10001` and with `--cap-drop ALL` (fallback to the host user);
  then strict mode (`-e AUDITGYM_REQUIRE_AGENT_USER=1`) in the default image, where the check must pass and no container
  test may be skipped, and with `--cap-drop ALL`, where the run must exit 2 with exactly one `error:` line. The
  container logs are uploaded as artifacts.

Latest completed run on `main` at the time of writing: run 44656432334, commit `af2fc47428dfbd9ebbee384c5b4c54d33ae95119`
(`test_container: a regex word boundary, not a backspace byte`), conclusion success. The lines cited here are kept in
[runs/ci/44656432334.txt](../runs/ci/44656432334.txt):

| Job | Result | Time reported by the job |
|---|---|---|
| check (ubuntu-latest, Python 3.11) | success | `PASS in 48 s` |
| check (windows-latest, Python 3.11) | success | `PASS in 41 s` |
| check (macos-latest, Python 3.11) | success | `PASS in 36 s` |
| container (network none, 2 CPU, 4 GB) | success; image 234 MB | `PASS in 67 s`; `time` reports 68.2 s; container tests: 9 ran, none skipped; `--user 10001` and `--cap-drop ALL`: `PASS in 63 s` and `PASS in 64 s`, `OK (skipped=8)`; strict mode: `PASS in 67 s` and 9 container tests `OK`; strict mode with `--cap-drop ALL`: `exit code 2`, one `error:` line |

No CI run has been executed on Python 3.12 or 3.13. The container job runs the image's default command, which is
`python -m auditgym check`.

## 14. Open items at this version

- Blank or over-long IDs make a submission invalid, as documented (section 4).
- The `runs/check` report was produced before this documentation pass; timings in it differ from the CI logs.
