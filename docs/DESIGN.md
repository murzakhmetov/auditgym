# auditgym design note

auditgym is a reproducible environment for training and evaluating financial-audit agents. One episode is
one synthetic company and one reporting period. The agent reads records through five tools, then submits
findings with evidence. A grader in another process scores them against an answer key that the generator
derived from a recorded causal change. Everything runs offline on the Python standard library (3.11; CI also runs 3.12 and 3.13 on ubuntu).

This note describes the current code (version 0.4.0). Version 0.4.0 changes every episode: `GENERATOR_VERSION` follows the package version and is part of `episode_id`, so a seed and config give another episode than under 0.3.0, and the 20
committed episodes and every record under `runs/` except the CI excerpts in `runs/ci` were regenerated. The historical day-1 plan is in [PLAN.md](PLAN.md).

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
Windows 10 with Python 3.11.4 locally, and in CI on ubuntu (Python 3.11, 3.12 and 3.13), macOS and Windows
(Python 3.11) and inside the container (section 13).

Sizes, currencies and counts (`config.py`, `catalog.py`). Sizes are `small`, `medium` and `large`. The 20 committed
episodes have 264 to 1,913 ledger rows, 94 to 200 documents (invoices plus payments) and 0 to 10 issues each. At most
12 errors per episode (`MAX_ERRORS`). An explicit count may be up to 2000 per key; `prior_invoices` may be 0. Six base
currencies are drawn at random (EUR, USD, KZT, JPY, KWD, GBP). AED, CHF, KRW and BHD are also accepted when given
explicitly; the organizer sweep ran them. The foreign pools also hold KRW, BHD, AED and CHF (`FOREIGN_POOL` in `auditgym/catalog.py`). Currency exponents are 0, 2 and 3
(JPY and KRW 0, KWD and BHD 3, the rest 2). Eleven built-in time zones are available, including DST rules and +05:45.

Invoice-count band. `min_read_pages` gives a lower bound on the pages a full read needs: one invoices row and two
ledger rows per prior, sales or purchase invoice, in pages of 50 rows. When the three counts together reach 1,651, the
request is a ConfigError at once (`counts too large for the 100-step budget`). Below that total, a count can still be
too large for the 100 steps; generation then fails after 16 attempts with exit 2 and the reason `budget_feasible`. One local run
at seed 5, other counts at their defaults (not committed; timings are not reproducible from the repo): 800 sales invoices generate in about 1 s; 900 fail after 16 attempts
(`full read needs 109 pages + submit > 100`) in about 14 s; 1,650 sales invoices fail at once with the ConfigError. So
the band from about 900 sales invoices up to the 1,651 total fails slowly.

## 2. Data contract

| File | Content |
|---|---|
| `public/manifest.json` | schema_version, generator_version, episode_id, company (synthetic), base_currency, currency_exponents, period_start/end, ledger_extract_end, timezone, record and document counts, rounding |
| `public/ledger.csv` | exactly `row_id,timestamp,account,debit_minor,credit_minor,currency,entity_id,invoice_id,payment_id`; empty field = null; base currency; one positive side |
| `public/invoices.jsonl` | doc_id, invoice_id, kind (sales/purchase), entity_id, issued_at, due_at, currency, total_minor, line_items[{line_no, description, quantity, unit_price_minor, amount_minor, ref}] |
| `public/payments.jsonl` | doc_id, payment_id, kind (receipt/disbursement/refund), entity_id or null, timestamp, currency, amount_minor, invoice_refs or null, bank_ref |
| `public/fx.csv` | date, source_currency, target_currency, rate (decimal string, 1 source = rate target); record ID `YYYY-MM-DD:SRC:TGT` |
| `public/policy.json` | UTC-offset schedule of the company time zone, period rule, FX date rule and publication calendar (holidays), conversion and rounding, posting/allocation/refund rules (a posting is booked at its own moment inside its document's period; amounts and rates follow the document), journal grouping, duplicate rule (line refs identify the supply; `issued_at` need not be identical: a copy keyed again later carries the later `issued_at` and is converted at the rate of its own local date; `issued_at` values are compared as instants, whatever offset each is written with; the amount is the later copy's posting), chart of accounts |
| `grader/truth.json` | issues (issue_id, type, variant, scenario, affected_ids, expected_amount_minor, currency, tolerance_minor, evidence_sets, explanation) and the doc-ID alias table |
| `grader/provenance.json` | seed, configs (sorted keys), attempt, history summary, injections with their semantic change, distractors (`posting_lag`, `credit_receipt` and the `remainder` entries of `split_payment` also name their `shape`), `posting_lags` (lagged documents of pairs and error issues, with shape and role), record-level ops (`add`/`remove`/`set` with before/after), `clean_digest`, `clean_records_digest` (order-independent hash of the reverted clean tables), `final_digest`, rejected attempts |

`load_episode` validates `grader/truth.json` against `schemas/truth.schema.json`, requires its `episode_id` to equal the manifest's, and requires `id_aliases` to map non-empty strings to non-empty strings. Bad input exits 2: every command that loads an episode directory (run, grade, verify, demo, transform, viewer, budget, and check section B) exits 2 with one `error:` line that names the file and the reason. The reasons are: `public/manifest.json` is not an object or has no string `episode_id`; any public or grader file is not valid JSON; a file is nested too deeply (a RecursionError); `truth.json` is not a valid answer key; or the answer key belongs to another episode. `python -m auditgym.check` maps the same answer-key and episode-format errors to exit 2, as `python -m auditgym` does. Before this rule, `verify` on a manifest without `episode_id` crashed with a traceback. In-memory episodes are not checked this way.

Times are ISO-8601 with an offset; the same instant may be written in UTC, company time or another offset
(`ts_repr`). Local dates always come from the policy's offset schedule. Money is integer minor units with the
currency exponent (JPY and KRW 0, KWD and BHD 3, others 2). The ledger extract covers the reporting period plus a
7-day cut-off window, with opening journals for items open at period start. IDs are opaque random tokens, unique
across tables, never sequential, and assigned the same way for injected and ordinary records.

## 3. Errors, variants, scenarios, distractors

| Type | Variants | Canonical affected_ids | Amount (base minor units) | Acceptable evidence sets |
|---|---|---|---|---|
| duplicate_invoice | same_day_copy, rekeyed_copy (sales or purchase side; the re-keyed copy is keyed 2 to 9 local days later, with its own issued_at and due date) | both invoice_ids | the later copy's primary row (1100 for sales, 2000 for purchase) | {doc A, doc B, primary row A, primary row B} (receivable or payable) or {doc A, doc B, counter row A, counter row B} (revenue or expense) |
| unallocated_payment | missing, partial | payment_id + invoice_id | amount wrongly credited to 2900 | {payment doc, invoice doc, payment's 2900 row, every 1100 row carrying the invoice ID (posting or opening item, relief by an earlier part payment, relief by this payment)} plus, for a foreign-currency invoice, the payment's bank (1000) row: 4 to 7 IDs (4 to 7 in the committed episodes) |
| wrong_fx_rate | utc_date, posting_date, stale_rate, transposed | invoice_id or payment_id | abs(posted - policy amount) | {doc, primary row, fx row of the correct date} or {doc, counter row, fx row} (invoices); {doc, bank row, fx row} (payments) |
| wrong_period | booked_early, booked_late, utc_wall_clock | invoice_id or payment_id | posted primary amount | {doc, primary row} or {doc, counter row} (invoices); {doc, bank row} (payments) |

A posting at another moment inside its document's own period is ordinary and no finding. `wrong_period` still means that
the posting falls in another reporting period than its document. `wrong_fx_rate` with variant `posting_date` still means
the rate of the posting's local date; the policy rate always follows the document's own local date, never the posting
moment.

Payment targets (version 0.4.0). A standalone `wrong_fx_rate` or `wrong_period` error sits on an invoice, a customer receipt or a
supplier disbursement. `config.resolve` draws the kind of every such error with `TARGET_KIND_SHARES` (invoice 0.34, receipt 0.36,
disbursement 0.30) on a fork of its own and stores it in the resolved config as `target_kinds`; the shares were tuned with the
document rules `a receipt`, `a disbursement` and `an invoice` of `auditgym.tells`, so that the three kinds are in the answer key at
about the same rate (precision 0.0225, 0.0231 and 0.0226 on 1000 episodes, base rate 0.022). A payment target comes with an invoice of
its own that it settles, in full or, for the `utc_date` and `utc_wall_clock` variants, partly (drawn like the boundary decoy
payments). That invoice takes a paid slot of its side (`error_invoice_load` gains `purchase_paid`), so the payments per invoice of an
episode do not depend on the number of errors. The payment never exceeds its invoice, nothing goes to 2900, and `derive_issues`
resamples a payment target whose allocation differs from the allocation in the clean books. The key of a `wrong_fx_rate` payment is
the payment ID, the amount is the difference between its bank row and the conversion at the policy rate, and the evidence is the
payment document, its bank row and the fx row of the correct date; the key of a `wrong_period` payment is the payment ID, the amount
is its bank row, and the evidence is the payment document and its bank row. A payment with a wrong rate takes posting lags like an
invoice with one (a lag is bounded by the clean posting moment and by the moved posting moment of a related document). The auditor
and the evidence checker read payment targets as before. Committed coverage, counted from the `truth.json` files: 8 standalone
payment-target issues in the 20 episodes, 3 on receipts (2 `wrong_fx_rate`, 1 `wrong_period`) and 5 on disbursements (2
`wrong_fx_rate`, 3 `wrong_period`), next to the 6 issues of the 3 boundary receipts. In the tells sample 716 of the 750 error
episodes name a payment in the answer key (0.9547) and 576 name one in a `wrong_fx_rate` or `wrong_period` issue (0.768), so a
policy that skips payments loses those.

Interacting scenarios:
- `boundary_fx_payment`: a partial foreign-currency receipt at the period boundary, with a wrong period and a wrong FX
  rate on the same payment. The receipt is placed just after local midnight (positive UTC offsets: from 00:05 on the
  first day after the period) or in the late evening of the period's last day (negative offsets). It is always booked
  by the UTC wall clock (`wrong_period`, variant `utc_wall_clock`). Its rate error is `utc_date` where the boundary
  gives that error an amount. Rates are published on weekdays only and a weekend date takes the latest earlier rate, so
  a positive offset needs the first day after the period to be a weekday, and a negative offset needs that day and the
  period's last day to be weekdays (`boundary_utc_date_ok` in `config.py`). In the other months the same receipt
  carries a `stale_rate` or `transposed` rate error instead. The two errors stay coupled (the `wrong_period` amount is
  the bank row posted at the wrong rate), but in those fallback months they have two causes, not one.
  `variants.wrong_fx_rate` only selects the fallback; the scenario uses `utc_date` wherever it has an amount. Where a
  DST change follows the boundary (America/New_York at the end of October when 1 November is a Sunday), the receipt is
  placed so that its posting stays 75 minutes clear of the change (`inject._clear_of_dst`).
- `fx_invoice_partial_allocation`: a foreign invoice booked at a wrong rate, then its receipt partly left in 2900.
  The scenario always uses the `partial` variant of the unallocated receipt (part relieved against the invoice,
  part left in 2900), so the receipt's 1100 relief and 7900 difference follow the invoice's wrong carrying amount.
  A configuration whose `unallocated_payment` variants exclude `partial` is a ConfigError.

Distractors (correct by policy): line-identical pairs of invoices of one counterparty on both sides (`legit_repeat`, below);
recurring monthly amounts (subscription refs are unique per supplier and month); split payments; one receipt for two
invoices; underpayments; overpayment plus refund; receipts without invoice reference (always at least one, so a 2900
credit is never a tell by itself); documents minutes before or after local midnight at the boundary, for invoices and
payments (`boundary_doc`, `midnight_fx`); weekend and holiday FX; near-midnight foreign documents converted on their
local date; postings booked at another moment inside their document's period (`posting_lag`); and receipts that credit
2900 without an error (the credit side, below). Default distractor counts per size are fixed in `auditgym/config.py`
(`DEFAULT_DISTRACTORS`: midnight_fx 2/3/4 for small/medium/large) or drawn from a range per size
(`DEFAULT_DISTRACTOR_RANGES` in the same file: boundary_doc 2-7, 3-8 and 4-8; posting_lag 12-22, 24-38 and 32-50;
overpayment_refund 1-3, 1-3 and 2-4; null_ref_receipt 1-3, 2-4 and 2-4; split_remainder 1-4, 2-5 and 2-6), so that no
count separates episodes with errors from clean ones. A twin option (`"twin": true`) rebuilds the same history with the
duplicate turned into a legitimate repeat: same ledger, opposite answer (train t03/t10). The twin keeps the whole
history for every seed.

Line-identical pairs and duplicates. The pair count T of an episode is drawn per size (`DEFAULT_REPEAT_PAIRS`: small
2-4, medium 3-5, large 3-6, on its own fork; stored in the resolved config as `repeat_pairs`) and holds the duplicates:
the D duplicates are converted pairs and the other T - D pairs stay legitimate repeats. When D is above the lower bound
of the range the decoys are drawn on top, so T = D + the drawn count and can leave the range. An explicit
`distractors.legit_repeat` N keeps its meaning (exactly N legitimate repeats, T = N + D) and so leaks the count for that
hand-written config. One pair builder serves decoys, duplicate sources and the twin. A pair is two invoices of one
counterparty, on either side (sales or purchase), with the same kind, currency, terms, total and lines apart from the
line reference, which is fresh: a supplier reference inside the description of a purchase, a delivery reference
`SO-{n5}` on a sales invoice (its line refs are `<ref>-<line_no>` instead of `L1..Ln`). In shape `same` both invoices
carry one instant; in shape `later` the second is keyed 2 to 9 local days after the first (never after the period's
last day), at an ordinary hour and with its own due date. The first invoice is paid with probability 1/2 and the second
never; side, shape, currency, price, item, terms and payment status are drawn without regard to what the pair becomes.
A duplicate is a converted pair: the first invoice stays, the second takes the first's line references and is posted as
the copy at its own `issued_at` and at the rate of its own local date. A `same` pair gives `same_day_copy`, a `later`
pair `rekeyed_copy`, and the amount of the issue is the later copy's primary row. With the twin option nothing is
converted: the chosen pair is relabelled `twin_legit_repeat`, so the twin has the same ledger rows and the opposite
answer, on either side and in either shape. Committed coverage, counted from the `truth.json` files: 7 duplicates in 5 episodes, 1 on a sales pair (d10) and 6 on purchase pairs (d03 twice, d07, d09, d10, t03), 3 `same_day_copy` (d03 twice and t03, all purchase) and 4 `rekeyed_copy` (d07 purchase, d09 purchase, d10 sales and d10 purchase). The train split holds only t03, a purchase `same_day_copy` (KZT): it has no sales duplicate and no `rekeyed_copy`; the dev split holds the other six. The committed twin pair t03/t10 is the purchase `same_day_copy` pair, and there is no committed sales twin. Two dev episodes have a foreign `rekeyed_copy` whose two primary rows differ, d09 (EUR base, GBP purchase invoices) and d10 (EUR base, GBP sales invoices), which
`test_a_committed_foreign_rekeyed_duplicate_has_two_different_postings` requires; `test_committed_set_covers_both_duplicate_sides_and_both_variants`
requires both sides and both variants.

Posting lag (round 8). Before round 8 the policy said that a posting's timestamp equals its document's, so any posting
at another instant marked an answer-key document (a `wrong_period` target, the `posting_date` variant, the boundary
receipt). On the 1000-episode tells sample the rule "a posting row at a different instant than its document" had
precision 1.000 (912 of 912 documents, recall 0.240) and the episode rule "any posting at a different instant" flagged
584 episodes, all with errors. Now `policy.json` says (`posting_rules.posting_timestamp`): "A posting is booked at its
own moment, which may be earlier or later than its document's timestamp (minutes, hours or days). That moment must fall
in the same reporting period as the document (see reporting_period.rule). It never changes an amount: amounts and
exchange rates follow the document (its local calendar date under fx.date_rule), never the posting moment." The
distractor `posting_lag` is a document whose posting is booked at another instant inside its own period. Its count is
the total number of documents of the extract whose posting is at another instant, the errors' own postings included,
drawn per episode on the config fork `distractor:posting_lag` (the lag draws themselves use the history fork `posting_lag`): 12-22, 24-38 and 32-50 for small, medium and large, about a quarter
of the documents (an explicit count may be up to 64; the other distractor keys up to 8). The lagged documents are drawn
uniformly from all eligible documents: clean documents, members of line-identical pairs (so a twin keeps the same
lags) and documents of error issues. Only the clean ones are recorded as `posting_lag` distractors, with their shape;
the pair and error ones go to the provenance list `posting_lags` with their role (`pair` or `error`). A document whose
posting is the error itself (a `wrong_period` target, the `posting_date` variant, the boundary receipt) never takes a
lag. A lag never crosses a period, and a posting keeps its place in the order against the documents it interacts with
(an invoice and the payments that settle it, the payments of one invoice), so a lag moves timestamps only, never an
amount, a rate or an allocation. The shapes are `later` (5 to 59 minutes, 1 to 24 hours, or 1 to 5 business days at
08-18 local), `earlier` (minutes, up to 30 hours, or 1 to 2 business days), `utc_wall_clock` (the instant minus the
zone offset, with a non-zero offset that is the same at the posting) and `date_change` (foreign-currency documents only:
another local date with another published rate, booked at the rate of the document's date; the hard negative for
`wrong_fx_rate` with variant `posting_date`). A count that cannot be placed resamples the attempt. An explicit count of
0 leaves only the errors' own postings at another instant and so restores the old tell: a diagnostic setting, for no
split and no check set.

Credit side (round 8). Receipts that credit 2900 are explained without errors, so that the rows on 2900, the
part-paid splits, the payments per invoice and the number of over-received invoices do not follow the errors.
`credit_receipt` (2-4, 3-5 and 3-6 per size, whatever the errors) has three over-received shapes: `overpaid` (an
overpayment that is never refunded), `settled` (a second receipt on an invoice that an earlier receipt settled) and
`topped_up` (a part payment of 30 to 60 percent, then a receipt above the rest and within the total, so the invoice
has a 1100 row and a 2900 row from two receipts); the share of `settled` and `topped_up` among them is drawn per
episode (uniform 0.2 to 0.9). `prepaid_receipt` is a receipt dated 1 to 8 days before the invoice it names, at most
the invoice total; it is 0 in half of the episodes and otherwise drawn (1-5, 1-6 and 1-7 per size), minus the planned
unallocated errors, so the unallocated errors take the place of prepaid receipts and not of over-received ones. In `provenance.json` a prepaid receipt is a `credit_receipt` entry with shape `prepaid`; `prepaid_receipt` is only the config key.
`split_remainder` (1-4, 2-5 and 2-6 per episode, on a fork) is a part payment followed by a second receipt that leaves
a rest of the invoice open: both relieve 1100 and nothing goes to 2900, so an invoice with two receipts below its total
is no tell for `unallocated_payment`. The invoice of every 2900 credit that is not a refund (the unallocated errors, the
over-received shapes, `overpayment_refund`, `split_remainder`) comes from one routine: an opening item (issued 3 to 30
days before the period) with probability 0.35 (`UNALLOCATED_PRIOR_SHARE`), otherwise an invoice of the period up to 8
days before its end, with loose dates (weekends included) and a size floor of 900 USD. Half of the unallocated errors
(`PART_PAID_SHARE`, on a fork named `earlier_payment`) sit on an invoice that an earlier part payment already relieved,
and the receipt is at most the open balance. The rows on 2900 that no refund and no null-ref receipt explains equal
`credit_receipt` + `prepaid_receipt` + the unallocated errors, whatever the errors are. The invoices that
`wrong_fx_rate`, `wrong_period` and the boundary scenario add are taken out of the drawn counts (resolved key
`error_invoice_load`; explicit counts stay exact and then the key is zero), and the opening items that fresh
unallocated receipts bring are taken out of `counts.prior_invoices` (resolved key `unallocated_prior`), so the invoice
count, the payments per invoice and the number of opening items do not follow the errors either. The policy's receipt rule says that an invoice that is not yet posted when the receipt is booked, or that earlier
payments have already settled, has no open balance to relieve, and the task text lists every relief (earlier payments and
this one) in the evidence of an unallocated payment. Every shape raises `SampleRetry` after 8 tries when a slot cannot be
filled, so no credit is silently lost.

Data realism (the shortcut audit and its fixes): target documents are ordinary draws. Quantities and unit prices
stay inside the catalogue ranges (no scaling), and ordinary invoices also clear the size floors used for targets.
Ordinary invoices and payments fall outside business hours, and some ordinary documents and non-FX targets fall on
weekends. Correctly booked receipts, disbursements and invoices are placed at the period boundary and near local
midnight in the same windows as the boundary errors. Duplicates and legitimate repeats share the same terms
(14/30/45 days) and payment-status distribution. Clean ledgers never overdraw the bank.
FX targets still never fall on a weekend or an FX holiday, because a same-day rate is required.
`python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells` measures 66 document rules (63 rules and 3 residual rules) and 17 episode-level rules on 1000 generated episodes (750 with errors; 3799 of 170,318 documents affected, a base rate of 0.022) and writes `runs/tells/summary.md` and `summary.json`, byte-identical across runs (about 3 minutes in a local run; the committed summary records no time). It also reports one pair-count document rule,
one pair-count episode rule and the table of duplicates by side and shape. No document rule reaches the spec limit
(precision 0.5 at recall 0.3) or the strong limit (precision 0.8 with three hits). The best document rule is the
amount-aware one on account 2900 (a payment with a 2900 row on an invoice that has no other payment, the payment at most
the invoice total: precision 0.239 at recall 0.111), which is the task's own reasoning about an open balance; the best pair rule, "line-identical pair, earlier member paid", reaches 0.161. A pair is a duplicate in 553 of 3,844 pairs (0.1439), and the four side-and-shape cells lie between 0.136 and 0.151 (sales/same 0.140, sales/later 0.151, purchase/same 0.136, purchase/later 0.148). The pair-count rule "pair member in an episode with at most 2 line-identical pairs" reaches 0.275, the weak prior D/T. The posting-lag rule "posting row at a different instant than its document" fires on 29,521 documents with precision 0.047 at recall 0.366, against 1.000 (912 of 912, recall 0.240) before round 8; the episode rule
"any posting at a different instant" flags all 1000 episodes with precision 0.750, which is the base rate (it flagged
584 episodes, all with errors, before). The document rule stays at about twice the base rate, because the `wrong_period`
and `posting_date` targets always differ in instant. The five other lag rules reach 0.051 (posted later, recall 0.170), 0.044 (posted earlier, recall 0.196), 0.057 (lag equal to the zone offset, recall 0.118), 0.012 (lag under one hour, recall 0.008) and 0.094 (a lag across a date change on a foreign-currency document, recall 0.209). The pair-count episode rule
"small ledger with at least 3 line-identical pairs -> error" reaches 0.6943 against 0.75. Thirteen of the 17 episode rules do not beat their base rate by more than 0.03; four do: "122 or more invoices -> error" (0.822 against 0.75), the small-ledger rules "at least 2 refunds -> clean" and "at least 3 null-ref receipts -> clean" (0.305 and 0.290 against 0.25), and "at most 5 documents posted later than their timestamp -> clean" (0.422 against 0.25; 90 episodes flagged, 38 correct; it was 0.247 on the 0.3.0 record). The cause of the first three is the size mix of `check_set`, which the tells sample uses: its clean entries are small, medium, large, small and medium, its five interacting
entries are medium, large, small, medium and large, and its ten mixed entries draw a size at random, so size says something about the label (in a 600-episode sample 152 of the 182 large
episodes were error episodes). The invoice counts do not differ by size between clean and error episodes (means 61.95
and 61.96 for small, 101.18 and 100.99 for medium, 123.93 and 123.83 for large), and a probe that draws the size independently of the
label finds the invoice-count rule at +0.017 and -0.055 over its base rate on two sets of 900 episodes. It is not changed here, because it would change `check_set` and every record derived from it. The lag-count rule is mostly the same effect (85 of its 90 flagged episodes are small, 5 medium, 0 large), but not entirely: among the 320 small episodes of the sample it fires on 36 of 100 clean and 49 of 220 error episodes (0.42 against a clean share of 0.31). That weak residual was not separated further; the figures come from a script outside the repository that tabulates `tells.generate_sample(1000)` by size and label. The largest foreign purchase is the FX target in 5 of 66 eligible episodes (0.076, chance 0.098). Off-hours payments are not only boundary receipts: 253 of their 506 hits fall outside the error window. Round 9 added six document rules for payments (`a receipt`, `a disbursement`, `an invoice`, `a payment in a foreign currency` and two readings of `a payment posted in another period`): precision 0.0225, 0.0231, 0.0226, 0.0351, 0.0120 (rows outside the period) and 0.0237 (timestamp outside the period), against the base rate 0.022.
`tests/test_tells.py` asserts looser limits than the figures above, on the 20 committed episodes (63 document rules, 17 episode rules): no rule with precision at least 0.5 and recall at least 0.3; no rule with precision at least 0.8
and at least three hits; episode rules at precision 1.0 with three hits (error rules) or 0.9 with two (clean rules).
On 100 generated episodes it asserts the window-by-kind and window-count rules, which the CLI does not measure, and the
pair and lag rules; on 80 generated episodes it asserts the credit and count rules; and it smoke-runs the CLI over the 66 rule names. The 0.239, 0.161 and 0.047 figures are
measured results of the 1000-episode run, not test limits.

Residuals left on purpose (round 8 hunts; the hunt scripts are outside the repository, the figures are from the round 8
notes and are not produced by `tells.py`). (1) A receipt with a 2900 row that is the first receipt of its invoice, is
dated after the invoice and is within its total is the task's own reasoning: the invoice had an open balance that covered
the receipt. A rule on it has precision 1.0 at recall 0.19 on documents and 0.07 to 0.15 on episodes. The only clean
negative would be a receipt booked before its invoice posts (the policy clause "an invoice that is not yet posted when
the receipt is booked"), which would touch the lag rules; it is not done. (2) Two rules predict the clean label: "no
receipt with a 2900 row dated after its invoice and within its total" (0.15 to 0.25 above the clean base rate on three
sets of 900 episodes, recall 0.1) and "at most one such receipt" (0.09 to 0.15 above it). An unallocated error always
adds one such receipt, and the per-episode share of `settled` and `topped_up` receipts only blurs it. (3) A comparator
that ignores the line reference is still exact on purchase invoices, because a purchase decoy carries its fresh
reference inside the description: precision 1.0 at recall 0.14 on purchase invoices; on sales invoices the same comparator has precision 0.09. It still compares every other
line field, so it is the duplicate test, not a trick. (4) Period-crossing proxies (a posting on another local date and
near the period end) are diluted forms of the definition of `wrong_period`; without the documents whose posting is in
another period they have precision 0.017, the base rate. (5) The size mix of `check_set` above.

Guards: injected monetary differences are at least 100 minor units (50 times the tolerance); FX targets fall
on dates with a published rate; unallocated targets are single-reference receipts whose amount is at most the invoice's open balance, with no other receipt on the invoice except an earlier part payment and no legitimate excess; (type, affected_ids) is unique per episode; at most 12 errors per episode
(`MAX_ERRORS`). The cited evidence of an unallocated receipt shows the invoice's open balance (its 1100 rows); `verify` checks on all public records that no receipt other than an earlier part payment touched the invoice and that the set is complete (sections 7 and 10).

## 4. Environment contract

`reset(seed, config, options)` returns `(observation, info)`. The config is a generator config,
`{"episode_dir": path}`, or either plus `"transform"`; `options={"config": ...}` is used when no config is given,
and other option keys are ignored. A generated episode needs an int seed: a bool, float or str raises `TypeError` that names the type (`generate_episode` itself accepts any seed; the stress run uses string seeds). In eval mode, a reset that generates an episode (`reset(seed=..., options={"config": ...})`, also in the `{"generator": ...}` form) from a seed of at most 40 bits (the bit length of its absolute value) with no secret still returns (observation, info), as section 04 of the case requires, and generation stays deterministic; but the env prints one line on stderr, once per env ("WARNING: eval mode generates an episode from a seed of N bits (at most 40) with no secret: such a seed can be recovered from the public `episode_id` and the answer key computed; ..."), and `info` carries `"weak_seed": true` for the host. The policy never sees it: both runners send the policy `protocol.policy_info(info)`, which drops the host-only keys (`protocol.HOST_ONLY_INFO_KEYS`); a reviewer's probe of round 8.1 found the flag in the child's reset info, and `test_a_policy_never_receives_the_weak_seed_flag` in `tests/test_env.py` now runs a spy policy through the isolated child. An empty secret counts as none. `AuditEnv(..., allow_weak_seed=True)` silences both for seeds that are public by design, as in tests and demos. Until round 8.1 such a reset raised `ValueError`; two reviewers scored that as a broken `reset` contract, so the refusal now lives only in the CLI's seeds-file paths. Train mode, `episode_id_for` and the generator version are unchanged, so committed episode IDs do not change (`WeakSeedInEvalMode` in `tests/test_env.py`). A config `"episode"` value that is not an `Episode` and a `"generator"` value that is not a dict each raise `TypeError` that names the type. When `"generator"` is in the config, any other top-level key outside the reset keys (`episode_dir`, `episode`, `generator`, `transform`) raises `ValueError` that names it. The first observation holds `task`, `manifest`, the full `policy`, and
`remaining_steps`. `step(action)` returns `(observation, reward, terminated, truncated, info)`. Python API in open training mode:

```python
from auditgym.env import AuditEnv

env = AuditEnv(mode="train")  # "eval": reward stays 0 until the grader reports; eval mode needs a secret, a seed above 40 bits, or allow_weak_seed=True (see above)
obs, info = env.reset(seed=123, config={"generator": {"size": "small", "errors": {"wrong_fx_rate": 1}}})
obs, reward, terminated, truncated, info = env.step(
    {"action": "list_records", "table": "ledger", "cursor": None, "limit": 50})
```

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
characters per finding, and a currency of at most `max_currency_chars` (8) characters. Every ID must be a non-blank string of at most `max_id_chars` (64) characters. An ID that
breaks this rule makes the whole submission invalid (reward −1), including an extra evidence ID; well-formed unknown
extra IDs are ignored. `claimed_amount_minor` must be an integer; an integral float such as `106965.0` is coerced to an
integer by the environment and by the `grade` command alike. Text that is not valid UTF-8 (a lone surrogate) in an
ID, in `episode_id` or in an explanation makes the submission invalid (reward −1).

100 steps including the submit; step 100 without a submit, or the time limit (`time_limit_s` in the task, 60 s by
default), truncates with an empty answer. Calls after the end return `episode_finished` and change nothing. In
`train` mode the terminal reward and TP/FP/FN are returned at the end; in `eval` mode the policy always gets 0.0 and
the grader keeps everything. Resubmission is ignored.

## 5. Isolation and leaks

The host process holds the episode, the answer key and the grader. The policy runs as `python -m auditgym.agent`
in a child process. The child gets:

- a temporary working directory whose only content is a staged copy of the agent-side code (`code/`, on the child's
  import path). On Windows the child's working directory is the empty `work/` subdirectory, which carries a Low
  integrity label (TEMP and TMP point there), and `code/` is read-only for the child (the integrity level is described
  below);
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
- a line that starts like a submit (its `"action"` key comes first, with the value `"submit"`) and breaks one of these
  limits, holds NaN or Infinity, or holds text that does not encode to UTF-8 ends the episode at once as
  `invalid_submission` (reward −1), as the same submission does in process and in `grade` (`validate_submission`
  rejects lone surrogates there); the trajectory stores `{"action": "submit", "findings": null, "invalid_action":
  <first 256 characters>}`, and a replay matches in status, reward and observations. A malformed submit whose
  `"action"` key is not first stays an `unknown_action` step;
- any other JSON value as the action, null included, goes to `env.step()`, which returns a bounded error;
- a stray `print()` goes to stderr and cannot desynchronise the protocol;
- a child that exits, crashes, or cannot be written to is an agent error: the episode is graded as an invalid
  submission (reward −1, `closed` false, status `agent_exited`), never as an empty answer, and `run` exits 3.
  Only the time limit and the step limit give empty answers.

Size is at parity too. A finding's `currency` is at most 8 characters (`MAX_CURRENCY_CHARS` in `schemas.py`: the
three-letter code plus whitespace around it), in `validate_submission` and in the published JSON schema. With that cap
every valid submission is below 830,000 bytes as `agent.py` serializes it (the bound is 828,755 bytes), far under
`MAX_LINE`. So a submit line over `MAX_LINE` is never a valid submission in process either.

The host hashes every file under `auditgym/` (bytecode included), `configs/*.json` and `schemas/*.json` before and
after each agent run. A change is an agent error (`agent_error`), and changed bytecode is deleted. The processes the
host tracks are killed when the run ends (process group on POSIX, Job Object on Windows). This detects tampering; it
does not prevent it.

Noninterference is tested by replay (`tests/test_noninterference.py`): five policies, in process and in the child,
on episodes whose answer key is shuffled, replaced by another episode's, or emptied. The agent's observations,
rewards and info are byte-identical (eval mode at every step; train mode up to the terminal step). Timing is not
covered, because the time limit is part of the contract. `tests/test_redteam.py` and `python -m auditgym.redteam`
probe hostile behaviour: 256 MB without a newline, 256 MB on stderr, two million short lines, an agent that stops
reading stdin, a flood of invalid UTF-8 that the agent never reads, and a grandchild process that must die with the
agent. In the flood (300 lines of 2,000,000 bytes of 0xFF) the host's peak must stay under (`QUEUE_LINES` + 7) ×
`MAX_LINE` = 22,000,000 bytes (the probe prints 21 MB, in units of 2^20 bytes): the 4 queued lines, up to 2 on the
reader's side (the line waiting for room in the queue, or the `readline` result being joined), up to 4 while
`receive()` decodes a line of invalid UTF-8 (its bytes, the decoder's 1-byte buffer and the string of 2 bytes per
character it widens into; 3 after the decode), which is 10 by count, and 1 line of margin. Peaks of 6 to 9.3 lines were
measured, on Windows only. A line of invalid bytes that also holds one character outside the Basic Multilingual Plane
decodes to 4 bytes per character instead (`sys.getsizeof` gives 8,000,068 bytes for a 2,000,000-byte line), and while
it widens the decoder holds the 2-byte and the 4-byte buffers together; such a flood was measured at up to 12.1 lines
(13 by count), over the probe's limit, which applies to the 0xFF flood only. For any input the bound stays a fixed number
of lines and does not grow with how much the agent sends, which is what the probe checks. Until round 7e.1 the probe allowed
`QUEUE_LINES` + 4 lines, which left out the decode, and failed in 6 of 12 full runs here; with the derived limit, 30 of
30 idle full runs and 10 of 10 runs alongside the organizer sweep passed. The grandchild probe needs the heartbeat file to exist and two reads one second apart, after the
agent is closed, to agree (a writer killed between truncating and writing leaves an empty file).

Limits: a child running as the same OS user is not a sandbox. Outside a container it can read files whose path it can
guess, and its parent's command line. Files the same user can read stay readable in every mode. The host's
environment, where `--secret-env` values live, is handled per platform. On Linux the host calls
`prctl(PR_SET_DUMPABLE, 0)` (`protocol.harden_host`) at the start of every command and before it starts its first
child, so a same-user child cannot read `/proc/<ppid>/environ`. CI
measured this on ubuntu-latest with Python 3.11, 3.12 and 3.13: `python -m auditgym.redteam --parent` prints "same user
as the host: the parent's environment is not readable" while its control with hardening off reads the variable, and
`tests/test_linux_hardening.py` asserts the same with a positive control. The kernel also refuses `/proc/<ppid>/mem` and ptrace to such a child; no test or CI step measures those two. On Windows the policy child lowers its own
token to Low integrity (S-1-16-4096) at the start of `agent.main()`, before any policy code loads (`agent._lower_integrity`;
it first relabels its own process object Low, which keeps `os.getppid()` working). Mandatory integrity control then refuses
`PROCESS_VM_READ` on the Medium host, so the child cannot read the host's environment block or memory. `python -m
auditgym.redteam --parent` prints "same user as the host: child at Low integrity, the parent's environment is not
readable (OpenProcess(PROCESS_VM_READ) error 5)", and its control with the lowering off still reads the host variable, so
the probe is not blind (measured locally and in CI on windows-latest, run 44775177143: [runs/ci/44775177143.txt](../runs/ci/44775177143.txt)). The `--policy-path` directory joins
`sys.path` only after the lowering, so no code in it runs at the host's level (`tests/test_windows_hardening.py` plants
`sitecustomize.py`, `argparse.py` and `ctypes.py` shadows). In a Windows venv the child starts from
`sys._base_executable` with `__PYVENV_LAUNCHER__` set, so its parent is the host and not the venv launcher
(`protocol.child_python`; the command-line probe of `python -m auditgym.redteam --parent` starts its child the same way).
`AUDITGYM_NO_LOW_INTEGRITY=1` in the host's environment turns the lowering off, and the `host hardening:` line of the probe
shows the switch. Only the values `1` (the user's switch) and `control` (the redteam control run) turn the lowering off,
in every place that reads the variable; any other value leaves it on. When the switch is `1` in the host's environment,
or when labelling the work directory fails, the host itself prints one line per process: "auditgym: warning: the policy
child is not lowered to Low integrity (<reason>); it can read this process's environment and memory". The redteam
control run stays silent, because it is a measurement. The child's own warning to its stderr remains as before. If
labelling the work directory fails, the child is not lowered and writes "auditgym: integrity level not lowered (label
failed: ...): the policy can read the host's memory" there. The price of Low integrity: the policy can write only in its
working directory, in TEMP/TMP and in directories that carry a Low label; every profile has one,
`%USERPROFILE%\AppData\LocalLow`, and files written there outlive the run. Its `--policy-path` directory, the
repository and default-labelled directories of the user profile (`%LOCALAPPDATA%`, caches with absolute paths) are
read-only, and a write there raises `PermissionError`, which is graded as an agent error (`agent_exited`, reward −1).
Reads of default-labelled files, subprocesses, `multiprocessing` and localhost sockets work. Residuals on Windows:
interpreter start-up (`site`, the standard library, user site, `usercustomize`) runs at Medium before the lowering; files
with a default label stay readable; and outside a container the child is still the same OS user. On macOS there is no
`/proc`: the probe reports "not measured on this platform (no /proc)" and nothing is hardened. Residuals on Linux: a
child with CAP_SYS_PTRACE is not blocked, and the negative assertions are skipped for a root test process;
`/proc/<pid>/cmdline` stays readable, so paths on the command line are visible; interpreter start-up runs before
`main()`; and an ancestor process that started with the variable in its own environment keeps it readable. `run`,
`generate` and `check` remove the `--secret-env` variable from their environment block once they have read it, so the
probe no longer finds it there, but the value stays in the host's memory. `tests/test_entrypoints.py` checks that `python -m auditgym` and `python -m auditgym.check` harden the host before they read the `--secret-env` variable. Inside the image the separate policy uid
blocks these reads (measured in CI on an ubuntu host only). The `--user 10001` fallback (host and child share one non-root uid) keeps the
Linux hardening, and the unit tests in that CI run, including the negative assertions, pass. The `--cap-drop ALL`
fallback runs the child as root without capabilities. Its `--parent` probe in CI (section 13) reads the same as the `--user 10001` run: hardening applied, the parent's environment not readable, and the control with hardening off readable. The unit tests' two negative assertions skip for a root test process, so the unit suite does not assert this; the probe is the only measurement. The container-only file tests are skipped under both
fallbacks. A process that leaves the
tracked group or job (for example with `setsid`) survives the run. Only a container or a separate OS user contains
that. The policy-adapter path (`module:Class`) follows the same rules: any class with `act(observation, reward, info)`
runs as `module.path:ClassName` (`--policy-path DIR` for code outside the repository); module names are validated before a
run starts (a module that exists but lacks the class fails in the child, exit 3), and the oracle is refused in the child (`examples/custom_policy.py`, `examples/hostile/`). `--policy-path` applies only to `module:Class` policies: a built-in policy name (random, recon, ...) never gets the directory on its import path (`runner.run_one` and `protocol.AgentProcess` drop it), so a file such as `random.py` in that directory cannot shadow the standard library and run as a built-in policy next to an answer key (`test_a_built_in_policy_never_sees_the_policy_path` in `tests/test_cli.py`).
`run` with a `module:Class` policy and closed data (a seeds file or `--secret-env`) refuses to start, exit 2 with one
`error: custom policy ...` line, when the policy would run as the host's user (no separate policy user, or
`--in-process`), unless `--allow-same-user` is given. The refusal says to drop `--in-process` on a host that can switch to the policy user, and to run the policy in the official image elsewhere. With the flag the run proceeds, prints one `WARNING` line and records `"allow_same_user": true` in `meta.json`, which is true only when the override took effect (a custom policy really ran as the host's user on closed episodes or next to an answer key on disk). That includes a fallback: when the guard predicted a switch to the policy user but `AgentProcess` still starts the child as the host's user (the account already has processes, or `chown` or `setuid` is refused), a custom policy next to closed data or an answer key is refused at that moment (`protocol.forbid_same_user_for_custom`, armed by the guard), exit 2 with a message that names `--allow-same-user`, unless the flag is given. With the flag the child runs as the host's user, one `WARNING` line names what is next to it (the closed episodes, or the answer keys with their `grader/` path) and says that the policy can read them and any file that user can read, and `meta.json` records `"allow_same_user": true` because the fallback took effect; when the switch works it stays false. The refusal comes when the child is created, so a built-in policy listed first may already have run in memory; nothing is written. The predicted-switch path and the fallback were tested with mocks only, because the development host is Windows; no run of this code on a Linux host with a real switch is recorded yet. In the official image the policy runs as the separate user and needs no flag;
strict mode (`AUDITGYM_REQUIRE_AGENT_USER=1`) still refuses any same-user fallback. A `module:Class` policy that would run as the host's user (no separate policy user, or `--in-process`) on an `--episodes` directory that has `grader/` and is not one of the committed episodes listed in `episodes/index.json` is refused too (the open train and dev episodes, whose answer keys are public by design, are exempt; a new folder placed under `episodes/train` or `episodes/dev` is not): `run` exits 2 with one line `error: custom policy <name> would run as the host's user next to answer keys (<dir>/grader): it can read them; <advice>, or pass --allow-same-user to accept that (recorded in meta.json)` and writes nothing. `<advice>` is "drop --in-process" on a host that can switch to the policy user and "run it in the official image (separate policy user)" elsewhere. With `--allow-same-user` the run proceeds with one `WARNING` line, and `meta.json` records `"allow_same_user": true` (only when the override took effect). The committed open splits need no flag and are not refused. Their answer keys are public by design, but a policy of the same user can read them, so `run` prints one `WARNING` line instead: `WARNING: custom policy <name> runs as the host's user next to the public answer keys of the open splits (<first dir>/grader[ and N more]): it can read them; fine for training, never for evaluation`, and `meta.json` records `"open_answer_keys_readable": true` (false otherwise; `allow_same_user` is untouched). The line is printed when the policy would run as the host's user (`--in-process`, or no predicted switch); it is not printed when a switch to the policy user is predicted, so a child that then falls back to the host's user on open episodes prints no open-splits WARNING (only the generic `auditgym: warning: policy runs as the host user` line) and records false. `examples/custom_policy.py` on `episodes/dev` exits 0 and prints the line. A run with closed data or foreign answer keys and `--allow-same-user` plus committed directories prints two `WARNING` lines. `test_jurors_probe_a_policy_that_globs_for_truth_json` in `tests/test_cli.py` covers the probe of a policy that globs for `truth.json` on a generated directory (it earned reward 1.0 with a warning before; now exit 2 and no output directory, and with `--allow-same-user` it runs and `meta.json` has `allow_same_user` true). A host can switch to the policy user (`protocol._can_switch_user`) when an agent account exists, `/proc` is listable and `CapEff` in `/proc/self/status` holds CAP_CHOWN, CAP_SETGID and CAP_SETUID. Root under `docker --cap-drop ALL` holds none of them, so it counts as unable to switch and the refusals above apply there; before this condition the guard returned early there and the child fell back to the host's user without a refusal. The built-in policies are unchanged: under `--cap-drop ALL` the check still falls back to the host's user with one warning line. `check --seeds-file` runs only the built-in baselines and the scripted auditor, so it is
unchanged. `python -m auditgym.redteam --parent` passes `--allow-same-user` to its probe run, because it measures exactly
that case; its report lines are unchanged.

Container: the environment and grader run as root; every policy child runs as uid 10002 (`agent`, no
supplementary groups, umask 077) in a temporary directory it owns, started with `Popen(user=, group=, extra_groups=[],
umask=)`; `close()` kills every process of that uid. `/app` is 0750 root:auditor and `/app/runs` 0770, so the agent can
neither read the package, seeds files or grader outputs nor write to the code; the host's environment is protected by
the different uid (other-uid `/proc/<pid>/environ` needs CAP_SYS_PTRACE). `tests/test_container.py` runs inside the image
in CI and must not skip (the policy cannot read the host's environment, a root-owned 0600 seeds file, a grader directory the host wrote or anything under `/app`, cannot write to the package, and every process of its uid is killed at the end of each episode); `--user 10001` and `--cap-drop ALL` fall back to a same-user child with one warning and still
pass. Only `PermissionError` falls back when the child is started (a refused `chown` of the staged tree falls back on `PermissionError` or `EINVAL`); any other start failure is an agent error, so the fallback cannot hide a fault.
Once a switch has worked in a process, a refused `chown` or `setuid` is an error, never a silent start as root; a host
whose `/proc` cannot be listed never switches, because `kill_uid` could not see the agent's processes.

Container use (organizers). Mount seeds files and episode folders under `/app` (for example
`-v $PWD/closed.json:/app/secrets/closed.json:ro`) and keep `--out` under `/app/runs`: a bind mount elsewhere keeps the
host's modes. The image writes the report to `/app/runs/check/report.md`. `--rm` removes the container, so to keep the
report, run it under a name, copy the file out and remove the container: `docker run --name auditgym-check --network none
--cpus 2 --memory 4g auditgym`, then `docker cp auditgym-check:/app/runs/check/report.md .`, then `docker rm
auditgym-check`. The copy-out commands above were not run locally; CI runs this pattern with `--name official` and `--pids-limit 512`
(section 13).

Strict mode (opt-in): with `AUDITGYM_REQUIRE_AGENT_USER=1` the fallback is an error (`AgentUserRequired`, not an
`OSError`, so it is never graded as an agent error). `check`, `run` (when it starts a child), `demo`, `viewer` and
`budget` start and stop one policy child first and exit 2 with one `error:` line before the first episode and before
any report. The image does not set it: a runner that adds `--user` or drops capabilities must still pass. CI runs the
check and the container tests in strict mode in the default image (none skipped), and checks that strict mode with
`--cap-drop ALL` exits 2 with exactly one line. To require the separate user for a run of the default image:
`docker run --rm --network none -e AUDITGYM_REQUIRE_AGENT_USER=1 auditgym`.

## 6. Matcher and reward

Normalization (`auditgym/matcher.py`): exact type (a finding of another type is a false positive, `tests/test_matcher.py` test_wrong_type_is_false_positive); affected and evidence IDs trimmed, deduplicated, compared
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

Diagnostics (`auditgym/diagnostics.py`; agent time is summed with `time.perf_counter()` around each policy call, because `time.monotonic()` ticks every 15.6 ms on Windows and left most committed agent times at 0.0 until round 8.2; micro and macro figures, miss reasons and FP causes are printed in `summary.md`
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
| provenance_roundtrip | revert-and-reapply reproduces the published tables; the reverted tables hash to `clean_records_digest`; `public_digest()` equals `final_digest`; every declared issue has an op that touches its records; injection and distractor IDs name existing invoices or payments in their role (the payment role needs a payment ID), truth issues and injections match one to one by (issue_id, type), targets are non-empty, every distractor has an ID list, and malformed injections and distractors give a FAIL line, not a traceback; an overflow during replay (for example a `1e400` amount) is a FAIL line too; a `provenance.json` that is not an object, or `ops` that is not a list, an op that is not an object or lacks a known table, ID, record or field, and a non-string issue ID give FAIL lines of this check (the replay and clean-books steps are then skipped), not a traceback. At generation time the reverted tables are also compared with the clean twin. It also cross-checks every `provenance.injections[].change` against the public records and the ops; an unknown, missing or malformed key of a known type is a FAIL line (details below). Not caught by `verify DIR` alone: see the list below the table |
| declared_discrepancies | the independent auditor (`auditor.py`, which imports only the standard library and `timeutil`: no generator module and not `money.py`; its FX conversion and proportional relief are its own integer arithmetic, tested against `money.py` on 10 000 random cases each in `tests/test_verify.py`) reproduces exactly the answer key: types, IDs, amounts, evidence sets; truth `id_aliases` equals `{doc_id: invoice_id or payment_id}` for every public invoice and payment (nothing missing or extra), every issue variant is a known variant of its type, and every issue's `tolerance_minor` is the published 2 (`task.TOLERANCE_MINOR`; the matcher trusts the key's value, so an inflated one would match any amount; `ToleranceInTheKey` in `tests/test_verify.py`) |
| evidence_sufficient | the separate evidence checker (`evidence_check.py`) re-derives type, IDs and amount from each evidence set alone, plus policy and manifest; dropping any record from a set breaks it, with no exception (`test_reduced_evidence_derives_nothing` drops each record in turn from every committed set). For `unallocated_payment` the checker derives the invoice's open balance from the cited 1100 rows and reads the ledger to see that the set holds every 1100 row of the invoice, requires the invoice's posting to be booked at or before the receipt's 2900 row and accepts the relief rows of earlier part payments booked before the receipt; `verify` also checks on all public records that no receipt other than such an earlier part payment touched the invoice and that the set holds every 1100 row of the invoice and, for a foreign invoice, the payment's bank row (below the table and section 10) |
| budget_feasible | reading every page of every table plus the submit fits in 100 steps |
| no_surface_tells | every injected or modified row has an untouched row with the same account and null pattern; in directory mode it fails when issues are declared but no ledger op exists |
| no_leaks | no answer-key markers or seed in public files |

The change cross-check of `provenance_roundtrip` (`verify.py`, `_ChangeIndex`, `CHANGE_KEYS`) works per injection type:

- `duplicate_invoice`: `change` is empty, for both variants.
- `wrong_period`: `posting_ts` is the timestamp that the ledger ops record for the target's booking rows.
- `wrong_fx_rate`: `correct_rate` and `correct_rate_date` are the `fx.csv` policy rate (the latest rate on the
  document's local date or in the 14 days before it). `wrong_rate` and `wrong_rate_date` are the rate found by the same
  rule for the date that the variant names (`utc_date`: the UTC date; `posting_date`: the local date of `posting_ts`;
  `stale_rate`: the day before the period). For
  `transposed` they are two adjacent digits of `correct_rate` swapped (at least 0.2 % apart, no date). The touched
  booking row (invoice 1100 or 2000, payment 1000) equals the amount at `wrong_rate`.
- `unallocated_payment`: `alloc` fits the variant (missing 0, partial more), 2900 holds the converted amount minus
  `alloc`, and the ledger relieves the invoice by the proportional carrying amount of `alloc`. `alloc` is checked only to
  the resolution of the base-currency 2900 and relief amounts.

The rates in `provenance.injections[].change`, and the `fx.csv` rate the cross-check reads, are checked against the
`fx.csv` format (`RATE_SYNTAX`: digits, an optional decimal part, no exponent, sign or space) before the cross-check
converts with them, so such a value cannot hang that step. A malformed rate in `fx.csv` itself is reported too. The
auditor (`_ratio`) and the evidence checker (`_rate_fraction`) accept only a plain ASCII decimal: at most 30 digits on
each side of the point and an optional exponent of at most 3 digits with an absolute value of at most 64 (`ValueError`
otherwise). `Fraction()` alone also reads `_` separators and non-ASCII digits, so a rate such as `1e9999_9999` would
otherwise reach `10 ** 99999999`; a very long rate (4,299 digits) gives no traceback either. `records_schema` flags a
rate that is not a positive finite number (`1e99999999` parses as `inf`). The auditor's failure is a FAIL line ("clean
books cannot be reconstructed: ValueError: ..." in `clean_equalities`, "the independent auditor cannot run:
ValueError: ..." in `declared_discrepancies`), and an evidence set that cannot be evaluated is a FAIL line of
`evidence_sufficient`. `verify DIR` on such a copy exits 1 within a second, with no traceback.

For `unallocated_payment` the acceptable set is the payment document, the invoice document, the payment's 2900 row,
every 1100 row that carries the invoice ID (its posting or opening item, the relief of any earlier part payment, and the
relief by this payment) and, for a foreign-currency invoice, the payment's bank (1000) row: 4 to 7 IDs, within the cap of
10 (`MAX_EVIDENCE_IDS`). The
evidence checker derives the invoice's open balance from the cited 1100 rows (debits minus credits, in the base
currency), not from the document total. It accepts a relief by another payment only when that payment was booked before the receipt (an earlier part payment: the
balance is what it left), and requires that the posted amount minus the earlier relief and this relief is positive, that the relief does not exceed what the receipt paid (the proportional carrying
amount), and that the invoice's posting or opening item is booked at or before the receipt's 2900 row (an invoice
booked after the receipt was not open when the receipt arrived). In the base currency the balance posted on the cited
rows covers the receipt, and the receipt equals its relief plus the 2900 amount. In a foreign currency the bank row is
required: the whole bank amount sits in 2900 when nothing was relieved, and 2900 holds less than the bank amount
otherwise. In a foreign currency the checker compares the receipt with the invoice document total, not with the open
balance in document currency, because ledger rows carry base amounts only and the payment-date rate is on no cited
record. The evidence checker also reads the ledger to see that the cited set holds every 1100 row of the invoice (a set that
leaves out an earlier relief shows a larger balance than the invoice had and derives nothing); `verify` checks the same
on all public rows.

`verify` reads all public payments and ledger rows for what the cited records cannot show: no payment but the issue's
own and earlier part payments (booked before it, relieving 1100 and leaving nothing in 2900) lists the invoice in `invoice_refs` (`_sole_receipt_errors`), no ledger row but those payments' relieves it
(a credit to 1100 for a sales invoice, a debit to 2000 for a purchase invoice), and every acceptable set holds every
1100 (2000) row of the invoice and, for a foreign invoice, the payment's bank row (`_complete_set_errors`). More than
one payment or invoice document that carries the issue's IDs fails too. In these checks a hand-edited record without a field (a
manifest without `base_currency`, an invoice without `currency`) is a FAIL line, not a traceback. So is an invoice or payment record without its ID field (`doc_id` and `invoice_id` in invoices, `doc_id` and `payment_id` in payments): `records_schema` and `ids_unique` give FAIL lines (`records_schema` names the record and lists its fields; `ids_unique` reads `<kind> record without <field>`, for example `payment record without payment_id`). An ID that is not text (null, a number, a list, an object) fails `records_schema` (`<table> <field> must be text, got <type>`). Later checks that cannot read such a record give a FAIL line of their own (for example `cannot run on records that fail records_schema: ...` from `provenance_roundtrip`), and `verify DIR` exits 1 without a traceback. In `ledger.csv` a missing `row_id` column is refused by the loader (`error: ledger.csv header mismatch`, exit 2), and a blank `row_id` fails `provenance_roundtrip` (exit 1); neither gives a traceback. The base currency is
read from `policy.json`, as the evidence checker does. `UnallocatedRecordsTests` in `tests/test_verify.py` enumerates
every subset of the issue's ledger rows (rows of the payment or of the invoice) together with both documents, for all 9
committed unallocated issues: exactly the key's set derives. The generator raises this type only for receipts on sales
invoices and the evidence checker refuses a purchase invoice, so the 2000 branch of the completeness check has no
generated case (section 10).

`verify DIR` without `--regenerate` does not catch, on its own: a changed `provenance.seed`, a removed or shortened distractor list, a distractor
kind swapped for another known one, a `wrong_period` injection variant, an injection's scenario (`verify` never reads it)
and a `truth.json` variant swapped for another known variant of its type (an unknown one fails `declared_discrepancies`).
An injection whose target values differ from the `affected_ids` of its truth issue fails
`provenance_roundtrip`, so a retarget to another existing invoice is caught. `verify DIR --regenerate` catches the seed, distractor and
variant cases: it regenerates the episode from its seed and config (the extra check `regenerates_from_provenance`) and compares every public and grader file byte for byte; `check` does the same on the committed episodes. An episode written with a host secret or by another generator version cannot be regenerated by the flag, so it prints a `SKIP` line with the reason and the exit code stays 0. The skip trusts the `secret_used` and `generator_version` fields of `provenance.json`, so an edited copy that also changes one of them gets a `SKIP` line and exit 0: a `SKIP` is not a pass. The flag is off by default and the nine named checks are unchanged. `tests/test_verify_regenerate.py` covers it, and four mutants in the mutation list (section 8) pin it.

`evidence_check.py` imports nothing from `auditor.py` or `money.py`. It reads UTC offsets from
`policy.utc_offset_schedule`, uses a fixed duplicate-signature field list (kind, entity, currency, total and every line item;
`issued_at` is not a field: the rule must say that it need not be identical when the instants differ, and equal instants
need equal row amounts; each cited row is its invoice's own posting in an account of its kind, booked in the period of its
invoice, and the amount is the later copy's row), derives nothing unless
`policy.duplicate_rule` names each field, and converts with `fractions.Fraction`. It shares only the ISO timestamp
parser and the `Episode` container. `tests/test_verify.py` cross-checks its conversion against `money.convert_minor`
on seeded random cases.

The digests are tamper evidence against accidental or casual edits, not a signature: someone who edits the ops and
recomputes the digests passes. `clean_digest` (the public digest of the clean twin) cannot be recomputed without the
twin's row order.

Independent recompute (round 9.1). `tools/recompute_keys.py` is a third derivation of the key next to the scripted auditor and the evidence checker. It reads only `public/` and the key's own fields (type, affected IDs, amount, tolerance, evidence sets) and imports nothing from `auditgym`; it recomputes the amount of every `wrong_fx_rate` (the bank or primary row against the document at the policy rate), `wrong_period` (the cited row, and that document and row fall on different sides of the period), `unallocated_payment` (the cited 2900 row) and `duplicate_invoice` (two identical invoices, the primary row of the later copy) issue, and for a payment target that nothing of the payment sits on 2900 and that it does not exceed its invoice. `python tools/recompute_sample.py OUT_DIR 100 --record runs/recompute` generates the sample of `tells.sample_entries(100)` and records [runs/recompute/summary.md](../runs/recompute/summary.md): 307 of 307 issues in 120 episodes (the 20 committed and 100 generated) are recomputed. It is a tool, not part of `check`, and it adds no test module, so the code stamp and the mutation pins are unchanged.

## 8. Reproducibility and paired checks

`transform.py` permutes rows, remaps every ID consistently in records, answer key and provenance, rewrites
timestamps as the same instants in another offset, and (`rename_seed`) replaces the company name and every invoice line
description with synthetic wording from a seeded injective mapping, in records and provenance, keeping reference tokens
such as `SUB-2025-05-6014`. `shift_years` moves every calendar year by K, a nonzero multiple of 28: the Gregorian weekday and leap-year pattern repeats every 28 years while no non-leap century year (1900, 2100) lies between the two dates, so the shift keeps every weekday, every 29 February and every n-th-weekday DST rule date of `timeutil.TZ_RULES`. Both ends of every date must stay inside 1901-03-01 .. 2099-12-31 and the period year inside 2000 .. 2100 (what `config.py` accepts); the date patterns also see years 2100 .. 2199, so a date in 2100 is refused instead of being left behind. The range is checked again on the shifted values after any `ts_repr` rewrite, because a UTC or local rendering can sit on another day than the source text. The episode ID tag gains `|shift{K}` and `transformed_from` records `shift_years`. Counterparties appear in the public records only as entity IDs, which the remap replaces. Issue numbering, affected-ID order and evidence order follow
content roles, not ID strings, so the oracle answer maps one to one.

The official check (`python -m auditgym check`) groups its named checks in the five rubric groups of `RUBRIC` in
`auditgym/check.py`. The section keys in `runs/check/report.json` are stable; the grouping is presentation only.
Sections:

- `F_contract`: 20 named contract checks in process on one hidden-like episode (`contract_battery.py`): reset and
  observation keys, 50-row pages, record keys in order, the same cursor twice and again after a fresh reset, unknown ID
  and action, calculator limits, submit and finished episodes, truncation at step 100 and not before, a frozen-clock
  time limit, eval hiding the reward, -1 for invalid and foreign submissions, the observation schema, and a 300-action
  seeded fuzz with a reset at every episode end (the fuzz draws from all four tables, so an empty table is exercised). Every group runs inside `try`, so a crash is a failed row.
- `E_leaks`: the observations of this run's hidden-like baselines (2093) hold only the allowed fields and no
  answer-key marker; oracle trajectories are never published.
- `B_committed_episodes`: each committed episode regenerates byte for byte from its seed and config and verifies.
- `B_replay`: recorded actions from `runs/train_dev/trajectories.jsonl`, for each split and policy (10 groups, the
  silent baseline included), replay in a fresh environment with JSON-equal observations and the same terminal reward.
- `C_data`: the hidden-like episodes verify. `sampling resamples (SampleRetry, BooksError or a sampling check) stay rare (N over M episodes)` counts the rejected attempts that were rejected by an exception (SampleRetry, BooksError) or by a sampling verify check (budget_feasible, no_surface_tells), and passes while that count is at most half the
  episodes; verification (correctness) failures are counted only by `no candidate episode was rejected by a correctness check`. On a closed path with fewer than four episodes this line is a SKIP (measurement only). The second line separates the kinds: each rejected attempt records the names of its failing checks, and the line passes when every rejection is for a sampling reason (SampleRetry, BooksError, budget_feasible or no_surface_tells). The correctness checks are records_schema, ids_unique, clean_equalities, provenance_roundtrip, declared_discrepancies, evidence_sufficient and no_leaks. On the hidden-like set 2 attempts were resampled, both for sampling reasons: `[PASS] sampling resamples (SampleRetry, BooksError or a sampling check) stay rare (2 over 20 episodes)` and `[PASS] no candidate episode was rejected by a correctness check (2 resampled, all for sampling reasons)`.
- `C_reward`: reward properties on every episode. On every error episode an attack battery runs: a type shotgun
  (one finding under each type), an amount ladder (neighbouring amounts), junk padding (the reward equals
  `clip(2F1 − 1)` exactly and stays below the answer alone), evidence stuffing (a true positive, by the published
  rule) and a right amount with the ID of an unrelated real invoice (not a true positive). Every distractor in the
  grader's provenance also becomes the most plausible false finding, built from the real records by the published
  rules: base currency, the posted base amount of the key row, the documents and rows the rules require, and for FX the
  neighbouring published date's rate. On an error episode it costs exactly one false positive when added to the oracle
  answer and matches no issue alone (an accusation that names only the records of an injected error is left out,
  and the line is SKIP only when every accusation of that kind is left out); on a clean episode it
  scores −1, below silence. An episode with no distractors, or whose accusations all name injected records, gets a SKIP line for that kind (an error episode with no distractors gets one line, `distractor accusations - no distractors in this episode`). Each such accusation must also match a decoy key that states exactly its claim and no
  decoy that differs in one criterion (type, IDs, currency, amount beyond tolerance, evidence), so a matcher that
  ignores any one criterion fails. `tests/test_check_battery.py` shows that the same constructors give true positives
  on the records of real issues. The baselines include `silent` (submits nothing at once); the check asserts
  auditor > silent.
- `D_paired`: same seed and config regenerate identical records and answer key; the same actions reproduce identical
  transitions (random explorer); isolated child and in-process runs agree; five transforms on every episode (permutation and ID remap; permutation, remap, mixed timestamps and renaming; remap and UTC timestamps; the 28-year shift; the shift combined with permutation, remap, local timestamps and renaming) and three single transforms (permutation, remap, renaming) on two error episodes keep the oracle answer and reward, and the auditor matches the same (issue, amount) pairs (133 checks on the public set). The shift uses +28; when the transform refuses +28 (a late period), it falls back to -28; when neither fits, the check is a SKIP with the reason "no 28-year shift keeps the dates inside 1901-03-01 .. 2099-12-31". On the public check set every episode takes +28. `python -m auditgym transform --in DIR --out DIR2 --shift-years 28` applies the shift, alone or with the other flags.
- `A_unit_tests`: the whole unit suite (`unittest discover`), reported as one check with run, passed and skipped
  counts.

Section counts list the checks that applied, and the skips in parentheses: `C_data 3/3 (1 skipped)` means three checks ran and one was skipped. The count appears in stdout, in `report.md` and in the viewer; `report.json` keeps `passed` and `total` and adds `applicable` and `applicable_passed`. The public check has no skips, so its lines did not change.

Each check report (`runs/check/report.md` and `runs/check/report.json`) carries a code stamp, and so do the organizer sweep's `summary.md` and `summary.json`: `code <sha256> (60 files), Python <version>, <platform>`. `code_sha256` is the sha256 of the canonical JSON of `protocol.code_digest()` without bytecode: the sources, configs and schemas under `auditgym/` (`auditgym/viewer/` is left out), `configs/*.json` and `schemas/*.json`. The one-liner `python -c "from auditgym.check import code_stamp; print(code_stamp())"` prints the stamp of the code in its checkout. The stamp holds no git commit, because a commit cannot contain its own hash. The committed `runs/check/report.md` carries a stamp that starts with `2b6130fb…` (60 files), which a clean checkout of this commit reproduces (`tests/test_hygiene.py` fails on a CR byte in any stamped file, because a local tool that rewrites a file with CRLF line ends changes the stamp). This is a different digest from the run-time hash of section 5, which includes bytecode. With the same code on the same machine only the timing fields of `report.md` and `report.json` change. The report header states the coverage (697 named checks of 83 kinds; a kind is one property, and most run on every episode they apply to) and whether the policy child ran as a separate user.

Unit tests rerun generation under two `PYTHONHASHSEED` values (`tests/test_generator.py`), and the committed schema
files must stay byte-equal to the generated ones (`tests/test_contract_fuzz.py`, test_committed_schema_files_equal_generated_ones).

Closed runs: `python -m auditgym check --seeds-file FILE --secret-env VAR --out DIR` runs sections C, D, E and F and
the replay of its own runs on the organizer's episodes. `run --seeds-file` and `check --seeds-file` (also `python -m auditgym.check --seeds-file`) without `--secret-env` exit 2 with one line `error: --seeds-file without --secret-env: anyone who knows the public records can recover a small seed from the episode_id; give --secret-env VAR (a host secret in that environment variable) or, for seeds that are public by design, --no-secret`. `--no-secret` is the explicit opt-out: the run proceeds, keeps the `WARNING` for seeds of 40 bits or fewer and records the opt-out (`"no_secret": true` in `meta.json` for `run`; the check report header reads `secret: no, --no-secret`). `--no-secret` together with `--secret-env`, or without `--seeds-file`, exits 2, and so does an unset or empty secret variable. The committed example passes: `python -m auditgym check --seeds-file examples/closed_seeds_example.json --no-secret` (summary `C_data 3/3 (1 skipped), C_reward 49/49, D_paired 20/20, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (101 named checks of 80 kinds)`). The `B_replay` labels `<split label>/<policy>` of a closed run count as one kind, as `train/<policy>` and `dev/<policy>` do in the full check. Checks that need error or clean episodes missing from the file are
reported as SKIP. An entry that the generator refuses (`ConfigError` or `GenerationError`, for example `boundary_fx_payment`
with `"timezone": "UTC"`) is a named SKIP line in `C_data`, "[SKIP] <name>: generated
from its seed and config - refused, ConfigError: <reason>", and the other entries are still checked and the report is
written. The header reads "seeds file <label> (N entries: G generated, R refused, secret: ...)" and the summary counts
the skip. The exit code is 0 when every check that ran passes. Only a seeds file in which no entry can be generated
exits 2, with one line "error: no entry of the seeds file can be generated; <name>: <reason>". `run --seeds-file` does the
same: each refused entry prints "WARNING: entry <name> refused, <reason>" and is listed in `meta.json` under
`refused_entries`; only a file with no generable entry exits 2. Each refused entry adds one named check (its SKIP line), and all refused entries together add one kind, because their names are stripped from the label; the seed-size warning looks only at the entries that were generated. It writes `runs/check_closed` by default, never `runs/check`. `--keep-runs` also writes trajectories and grades, which
contain the closed answer key. CI runs it in the image with the seeds
file and the output directory mounted, `--network none` and strict mode. `python tools/organizer_sweep.py DIR 60
--record` runs it over the stress mix plus one boundary configuration per edge value that `config.py` accepts
(428 configurations, 423 feasible; 63-bit seeds, a host secret, chunks of 60: seven chunks of 60 episodes and one of 3) and runs the contract battery in
process on every feasible episode. On the code of `5663020` (code stamp `2b6130fb…`, the same as the check report's) the sweep ([runs/sweep/summary.md](../runs/sweep/summary.md)) had 8 chunks, all exit 0; every contract battery passed and
no feasible configuration failed to generate. Date-shift checks are skipped, as the chunk rows of the summary show: the two shift transforms on the boundary configurations `bnd_period_last_supported` and `bnd_period_century_february`, whose dates no 28-year shift in either direction keeps inside 1901-03-01 .. 2099-12-31 (chunk 6 shows the 4 skipped `D_paired` checks); chunk 7, which holds the last 3 episodes, also lists skips (`C_data` 1, `C_reward` 4, `D_paired` 1). In an earlier round a sweep failed one chunk on "no agent process failed" because a package file had been edited while that chunk ran; the line now names the failing runs, and a sweep is recorded only without edits. A sweep takes about 20 minutes or more on Windows 10 (earlier local runs took 18 and 21 minutes; the 428-configuration sweep was not timed); the summary records no time. The 5 infeasible configurations (the `UTC` time zone twice and invoice counts at the maximum three times) each raise a ConfigError that names the reason (the Europe/London configuration with `wrong_fx_rate` limited to `utc_date`, which one seed could not place in round 8.2 with `no feasible variant of wrong_fx_rate for this configuration`, generates in this sweep; the outcome is seed-dependent); the three count configurations have a total of 1,651 or more invoices and are rejected at
once because a full read would need more than 100 steps; section 1 gives the band below that (`config.min_read_pages`: one invoices row and two ledger
rows per counted invoice, a lower bound that a unit test checks on every committed episode).

### Mutation run

`python tools/mutation_smoke.py OUT_DIR [--record] [--jobs N]` asks how strongly the unit tests pin the core. It holds 200 hand-written one-line mutants of `matcher.py`, `reward.py`, `grader.py`, `schemas.py`, `env.py`, `verify.py`,
`evidence_check.py`, `protocol.py`, `transform.py`, `agent.py`, `check.py`, `check_battery.py`, `config.py`, `inject.py`,
`history.py`, `auditor.py`, `policy.py`, `books.py`, `tells.py` and `__main__.py` (20 files; the
summary's file list is generated from the mutant list). The list grew from 126 to 180 in round 8, to 183 in round 8.2 to 196 in round 9 (13 mutants for the payment targets) and to 200 for `verify --regenerate` (4 mutants). Four mutants were added in round 7e: `cli-keys-refusal`, `protocol-cap-setuid`, `check-no-secret-refusal` and `env-weak-seed-bound`. Among the 180 are the mutants for the unallocated evidence rules
(for example `evidence-unallocated-booked-after`) and for the boundary rule and its fallback
(`config-boundary-utc-date-positive`, `inject-boundary-fallback`, `config-boundary-fallback-refusal`). Each mutant runs in a fresh temporary copy of the
repository (the working tree is never touched), first against the unit-test modules listed for it and, only if those
pass, against `tests/test_mutation_survivors.py`. That module was written for the mutants that the first run let survive.
A timeout counts as a kill; the tool stops the whole process tree of a timed-out test.

Result ([runs/mutation/summary.md](../runs/mutation/summary.md), recorded on Windows with Python 3.11): 200 of 200 mutants are killed, none survived and none is equivalent (in round 9 `history-paid-slots-ignore-load` first survived, because the payment targets moved the load that the test killing it relied on, until `test_the_paid_slots_of_a_side_always_number_the_drawn_invoices_and_keep_the_paid_share` was added). The test modules listed for each mutant kill 152 of them. The other 48 pass their listed modules and are killed by `tests/test_mutation_survivors.py`; the remaining
test modules were not run against them, and some of those kill a few of them too (for example `tests/test_contract_fuzz.py`
kills `schemas-blank-id`, `schemas-coerce-int` and `env-submit-extra-keys`). The summary's "killed by" column says "listed tests" or "survivor tests". One mutant
(policy-path-append) is killed only by a Windows-only test, so the tool runs it only on Windows and reports it as "not run
here" elsewhere. The run takes more than 10 minutes with `--jobs 4` on the local machine (13 minutes with 135 mutants; the 180 were not timed). `summary.json` records a
sha256 of every test module the run used, and `tests/test_mutation_smoke.py` fails inside `check` when a test module
changed after the recording or when the mutant list no longer matches the code.

### Run outputs and exit codes

`runs/*/trajectories.jsonl` holds one line per record with `run_id` (`split:policy:seed`), `split`, `policy`,
`episode_id`, `step`, `action`, `observation`, `reward`, `terminated` and `truncated`. Step 0 is the reset observation,
with `action` null and reward 0.0. The terminal reward is written into the last record of each episode after the run;
in eval mode the policy itself received 0.0 at every step. Oracle runs never appear in trajectories. A malformed
submit that ends the episode (section 5) is recorded as `{"action": "submit", "findings": null, "invalid_action": ...}`.

`runs/train_dev/meta.json` records the versions (auditgym, generator, config, schema, grade), the Python version
(3.11.4 locally), the platform, the mode, the policies, the command, `secret_used`, `no_secret`, `allow_same_user`, `open_answer_keys_readable` and `refused_entries`. The committed file was
written on Windows 10. Exit codes: 0 pass; 1 a check or verification failed; 2 bad input (one `error:` line on
stderr, for example an unknown policy or an unset `--secret-env` variable); 3 the run finished but an agent process
failed (crash, exit, or tampering with the graded code). The `no agent process failed` line of section C_reward names up to three failing runs, each as `policy on episode: agent error`, and each entry is cut to 200 characters.

## 9. Measured results

Numbers are copied from generated files. The full tables are in [README.md](../README.md#evaluation) (and
[README.ru.md](../README.ru.md)); the sources are `runs/check/report.md` (hidden-like set),
`runs/train_dev/summary.md` (open splits), `runs/budget/summary.md` and `runs/stress/report.md`.

Hidden-like set (20 episodes from the public master string `auditgym-check-v1`, eval mode, isolated agents):

| Policy | Return | F1 | Micro P | Micro R | Steps | Closed share | FP on clean |
|---|---|---|---|---|---|---|---|
| oracle (grader-side) | 1.000 | 1.000 | 1.00 | 1.00 | 0.0 | 1.00 | 0 |
| scripted auditor (verifier code) | 0.9349 | 1.000 | 1.00 | 1.00 | 32.55 | 1.00 | 0 |
| recon (simple reconciliation) | −0.6835 | 0.183 | 0.10 | 0.71 | 32.55 | 0.00 | 87 |
| silent (submits nothing at once) | −0.500 | 0.250 | n/a | 0.00 | 0.0 | 0.25 | 0 |

The empty answer scores −0.500: +1 on the 5 clean episodes and −1 on the 15 error episodes. Recon and the random
explorer score below it; only the scripted auditor and the oracle beat it.

Recon's misses on this set are all `not_flagged`: its recall is 0.65 on FX, 0.8125 on period errors and 1.0 on unallocated receipts, and 0.3333 on duplicates. Recon groups duplicates on purchase invoices only (account 2000), compares the calendar date as
written and ignores the line references, so it misses the sales duplicates and the re-keyed copies; its recall on duplicates
was 1.0 on this set before duplicates came on both sides and in two shapes (0.3333 on this set now; dev 0.6667 and train 1.0, where the one train duplicate is a purchase same-day copy, which recon finds). Recon's return fell after the data shortcuts were removed (commit `a94d9b9`,
parent `bb80adb`): dev −0.545 → −0.689 and train −0.638 → −0.690 (`git show a94d9b9^:runs/train_dev/summary.md`
against `git show a94d9b9:runs/train_dev/summary.md`), and the hidden-like set −0.490 → −0.589 (`git show bb80adb:runs/check/report.md` against `git show a94d9b9:runs/check/report.md`). The
scripted auditor barely moved (dev 0.947 → 0.943; train 0.970 → 0.971). Measured with `python tools/recon_drop.py` (about 30 s; synthetic medium episodes, not the committed splits; the seeds are not paired across the two trees, because the generator changed). Of 80 `wrong_fx_rate` targets recon missed 3 at `bb80adb`; of 80 it missed 22 at `a94d9b9`. At `a94d9b9`, 10 targets are documents dated on a day without a published rate, which that commit books at the latest earlier published rate; recon looks a rate up by the document's own date and missed 10 of them. The other 12 misses (against 3 before) have a rate on their date and are not explained. On 30 error episodes with one error of each type, recon's recall fell for FX (0.933 → 0.800), period errors (0.933 → 0.867) and duplicates (0.967 → 0.933), and its false positives per episode rose on 30 clean episodes (7.20 → 7.83) and on the error episodes (7.37 → 8.13). These shares are measured, not isolated. The tool extracts each commit with `git archive` into a temporary directory and writes nothing to the repository.

Open splits: scripted auditor return 0.969 (train) and 0.9426 (dev); recon −0.7247 and −0.7328; silent −0.400 and −0.600. On dev, recon misses are all
`not_flagged` (recall 1.0 on unallocated receipts, 0.3333 on duplicates, 0.5556 on FX and 0.625 on period errors; on train 1.0, 1.0, 1.0 and 0.5). Random and flag-everything
misses on dev are all `search` (they never observed a complete evidence set); on train, flag-everything has one `not_flagged` miss and nine `search` misses and random only `search` (`runs/train_dev/summary.md`). Macro P and R count clean episodes as 0, so the oracle sits at 0.7
(train) and 0.8 (dev); micro P and R are the figures to read.

Action budget (dev, scripted auditor and recon; `python -m auditgym budget`): auditor F1 0.367 at 20 steps, 1.000 at 50 and 100; recon F1 0.051, 0.156 and 0.156. The default budgets are 20, 50 and 100 steps; `make budget` runs the same command
where make is installed. At 20 steps the scripted auditor closes 3 of the 10 dev episodes (return −0.2807) and recon returns −0.9142; at 50 and 100 steps the returns are 0.9426 and −0.7328.

Generator stress (`python -m auditgym stress --n 300`): 300 random configurations, 299 generated and verified (270 at the first attempt, 29 later), 1 infeasible with a ConfigError (a request for the `UTC` time zone, which never has a UTC offset),
no verify failures and no generation failures; 17 extreme configurations all verified, and the scripted auditor closes all of them in 11 to 48 steps. The 17 extreme configurations are 12 errors in each of the 11 time zones, three
currency-exponent mixes, a year boundary, Sydney DST and one large episode with 12 errors. The whole stress run took about 400 s on the machine that produced `runs/stress/report.md` (from the timestamps of the record log). Timings and memory are machine-dependent, counts are not.

Feasibility: an unspecified time zone or period is redrawn (on a side RNG stream, so feasible draws and the committed
episodes are unchanged) until the requested errors can be placed. With the default variants all 36 months of 2025–2027
host `boundary_fx_payment` with a fixed period: where the boundary gives `utc_date` no amount, the same receipt carries a
`stale_rate` or `transposed` rate error (section 3). A ConfigError remains in three cases. First, a fixed time zone with a zero
UTC offset at the boundary (`UTC`, Europe/London in winter) is refused for the offset alone, also with default variants.
Second, when `variants.wrong_fx_rate` has neither `stale_rate` nor `transposed`, a month in which the boundary gives
`utc_date` no amount is refused, and the ConfigError names the nearest feasible months: 11 of the 36 months with a
positive or unset offset and 17 with a negative one. The counts follow from `boundary_utc_date_ok(period, offset)` (a
positive offset needs the first day after the period to be a weekday; a negative offset needs that day and the period's
last day to be weekdays): `python -c "from auditgym.config import boundary_utc_date_ok as ok; ms=[f'{y}-{m:02d}' for y in (2025,2026,2027) for m in range(1,13)]; print(sum(not ok(p,60) for p in ms), sum(not ok(p,-60) for p in ms))"` prints `11 17`. The first two cases give a one-line ConfigError. The third case is a request that limits `wrong_fx_rate` to `utc_date`: it can be refused after the redraw, when the drawn history has no candidate document (one sweep configuration, `bnd_tz_Europe/London_utc_wall_clock`, was refused this way in round 8.2 and generates in the 0.4.0 sweep; seed-dependent), with the same kind of error. The generator never silently injects fewer errors than requested. `check` fails if
resampling exceeds half the number of episodes in the check set.

## 10. Limitations

Also listed in [README.md](../README.md#limitations) and mirrored in [README.ru.md](../README.ru.md).

- **Platforms.** Local runs: Windows 10, Python 3.11.4. CI: ubuntu with Python 3.11, 3.12 and 3.13; macOS and Windows with Python 3.11 (the workflow
  pins only the minor version; the patch version is not in the committed CI excerpt), and the container. `pyproject.toml` sets `requires-python = ">=3.11,<3.14"` (CI runs 3.11, 3.12 and 3.13), so Python 3.14 is outside the range and was not tested. The POSIX process-tree branch
  runs in CI, not locally. The Linux host hardening (section 5) is measured on ubuntu only; the Windows Low-integrity lowering is measured on windows-latest and locally; macOS is not measured.
- **Container.** Built and run in CI with `--network none --cpus 2 --memory 4g --pids-limit 512`. Inside the image
  the host runs as root and every policy child as uid 10002 (`agent`, section 5). Under `--user 10001` or
  `--cap-drop ALL` the policy falls back to the host's user with one warning line; under `--user 10001` the Linux
  hardening of section 5 still blocks the child's read of the host's environment (measured in CI); under
  `--cap-drop ALL` the child runs as root without capabilities. The `--parent` probe in CI measured the same readings as under `--user 10001` (one ubuntu Docker host), but no unit test asserts them, because the negative assertions skip for a root test process. On Windows the child runs at Low integrity and cannot read the host's
  environment block (measured outside a container; section 5); with the lowering off it can. `--secret-env` is removed from that block after reading (measured), but its value stays in the host's memory; the Low-integrity child cannot read that memory (the probe's `OpenProcess(PROCESS_VM_READ)` returns error 5). CI also runs the closed check in the image with a mounted seeds file and output directory, in strict
  mode.
- **Isolation** is a process boundary, not a sandbox (section 5). Open train and dev answer keys sit in the repository
  by design, so a child running as the same OS user can read them.
- **Seeds.** The generator is open source. With no host secret and a guessed config, a small seed can be recovered from
  the manifest's `episode_id` (`episode_id` is `ep_` plus the first 16 hex digits of SHA-256 over
  `auditgym|<generator version>|<seed>|<canonical config>|<secret or empty>`, followed by `|twin` for twin episodes and
  then `|episode_id`; the canonical config leaves out `twin`), and the answer key can then be
  regenerated. Use 63-bit seeds and `--secret-env`. This is partly closed, and still a limitation: `run --seeds-file` and `check --seeds-file` refuse a seeds file without `--secret-env` unless `--no-secret` is given (section 8), and `AuditEnv(mode="eval")` warns once and sets `info["weak_seed"]` when it generates an episode from a seed of 40 bits or fewer with no secret (section 4). The env does not refuse, because the case requires `reset(seed, config)` to return (observation, info); so a host that resets a raw env in eval mode with a 13-bit seed and no secret can still have that seed recovered from the `episode_id`, and the warning and the flag are what tell it. A seed above 40 bits without a secret, or any seed when the secret is known, can still be regenerated by anyone with the config. Public records allow brute-forcing small seeds in any case.
- **Hidden-like set.** It comes from a public master string. It tests the pipeline, not secrecy; closed evaluation
  uses `check --seeds-file`.
- **Scripted auditor.** It shares `auditor.py` with the verifier. Its perfect F1 shows that every scenario is solvable
  through the tool interface within the budget, not that an agent would reason this way.
- **Unallocated payment evidence.** The cited set (the payment, the invoice, the payment's 2900 row, every 1100 row of the
  invoice and, for a foreign invoice, the payment's bank row) shows the invoice's open balance (relief by earlier part payments included); `verify` checks on all
  public records that the set is complete and that no other receipt settled the invoice (section 7). In a foreign
  currency the checker compares the receipt with the invoice document total, not with the open balance in document
  currency, because ledger rows carry base amounts only; completeness of the cited 1100 rows is checked by `verify` on
  all public rows and by the evidence checker. Purchase-side unallocated issues are not generated: the generator raises
  this type only for receipts on sales invoices, and the evidence checker refuses a purchase invoice. An open-items
  listing is still not offered: [CASE.md](CASE.md), "Open records", defines the open records, and none of them is an
  open-items listing; a new record type would change the tool contract that organizer policies run against.
- **Shortcut tells** are measured only for the rules written down in `auditgym/tells.py` (section 3). A feature nobody
  listed may still leak. The residuals left on purpose are listed in section 3: the sole-receipt reasoning on account 2900,
  the clean-predicting rules on receipts after their invoice, the ref-blind comparator on purchases, the size mix of
  `check_set` and the floor of the posting-lag rule.
- **Error targets.** Done in round 9 (version 0.4.0). A standalone `wrong_fx_rate` or `wrong_period` error sits on an invoice, a customer receipt or a supplier disbursement (section 3, "Payment targets"), so a policy that skips payments loses them: 576 of the 750 error episodes of the tells sample name a payment in such an error (0.768). Refunds still never carry an error.
- **Diagnostic settings.** An explicit `distractors.posting_lag` of 0 restores the posting-instant tell, and an explicit
  `legit_repeat` leaks the pair count; neither belongs in a split or a check set (section 3).
- **Evidence padding.** Extra evidence IDs up to the 10-ID cap are free (published superset rule); the battery checks
  that padding stays a true positive and does not penalize it.
- **Paired transforms** cover row order, ID remap, timestamp representation, renaming and a date shift in whole 28-year
  steps (the weekday and leap-year cycle). A shift by another number of years would change weekdays and DST rule dates,
  so it is refused; late periods cannot shift forward and use -28, and dates must stay inside 1901-03-01 .. 2099-12-31.
- **Accounting model.** Deliberately small: base-currency ledger, payments in the invoice currency, no taxes, credit
  notes or cross-currency settlement, eleven built-in time zones instead of the IANA database.
- **flag_all** is a format-level attack: it reads first pages and uses document amounts. Smarter attacks are covered by the reward battery in `check` (section 8).
- **Invoice counts.** A total of 1,651 or more invoices is a ConfigError at once; counts from about 900 sales invoices up to that total pass validation and fail after 16 attempts with exit 2 (section 1).
- **Directory verification.** `verify DIR` without `--regenerate` accepts some edited copies (a changed `provenance.seed`, a removed or shortened distractor list, a distractor kind swapped for another known one, a `wrong_period` variant, an injection's scenario, a `truth.json` variant swapped for another known one); section 7 lists them, and `--regenerate` catches them. An invoice or payment record without its ID field or with a non-text ID is a FAIL line, not a traceback (section 7).
- **Episode size.** The case suggests 20 to 200 documents per episode. The size `large` gives 202 to 251 documents in 24 sampled seeds (ledger rows stay within 2,000), and 9 of the 20 hidden-like episodes of `check`, all `large`, have 207 to 242 documents. The committed episodes are inside the suggestion (264 to 1,913 ledger rows, 94 to 200 documents): d09 and d10 carry explicit `counts`. Lowering the `large` preset would change every large episode and every record derived from it, so it is left as it is.
- **Noninterference** is measured by replay (section 5). Timing is not covered, because the time limit is part of the contract.
- **boundary_fx_payment feasibility.** With the default variants every month of 2025–2027 hosts the scenario. A fixed zone with a zero UTC offset at the boundary (`UTC`, Europe/London in winter) is refused, and so is a month where the boundary gives `utc_date` no amount when `variants.wrong_fx_rate` has neither `stale_rate` nor `transposed` (11 months with a positive or unset offset, 17 with a negative one; section 9). A closed seeds file with such an entry reports it as a SKIP line and checks the rest (section 8). In the fallback months the two errors of the scenario have two causes, not one (section 3).
- **DST and standalone period errors.** Fixed in round 8.1: the boundary receipt and a standalone `utc_wall_clock` `wrong_period` error both use `inject._clear_of_dst`, so their UTC-wall-clock posting stays 75 minutes clear of a DST change and keeps the boundary's offset. Before, in America/New_York in October 2026 (1 November is a Sunday) 22 of 40 seeds posted inside that window, a time ordinary documents never use; now 0 (`StandaloneUtcWallClockDstTests` in `tests/test_generator.py`, mutant `inject-utc-wall-clock-dst`). Where no DST change is near the boundary the minute range and the draw are unchanged, so only configs with such an error on a DST boundary night produce other episodes than at commit `cd7794b` under version 0.3.0; the committed episodes are byte-identical.
- **Evidence IDs and amounts.** A blank or over-long ID (more than 64 characters) makes the submission invalid, even as
  an extra evidence ID. Both are kept in this version: the task publishes `max_id_chars` and also says unknown extra IDs
  are ignored. An
  integral float `claimed_amount_minor` (`106965.0`) is coerced to an integer by both the environment and `grade`. Text that is not valid UTF-8 (a lone surrogate) in an ID,
  in `episode_id` or in an explanation is invalid too. A malformed submit whose `action` key is not the first member is
  one `unknown_action` step. A submit over `MAX_LINE` is never valid, in the child or in process (section 5).
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

- Job `check` with `PYTHONHASHSEED=0` on `ubuntu-latest` (Python 3.11, 3.12 and 3.13), `windows-latest` and `macos-latest` (Python 3.11):
  `python -m auditgym check`; then `python -m auditgym.redteam --parent` (on every platform; its lines are printed in the job log); then `build-splits` and `schemas`, followed by `git diff --exit-code` on `episodes` and
  `schemas`; then a replay of the open splits, followed by `git diff` on `runs/train_dev/trajectories.jsonl`. The
  check report is uploaded as an artifact.
- Job `docker` on `ubuntu-latest`: `docker build -t auditgym .` (base `python:3.11.10-slim-bookworm`), `docker image ls`,
  then `time docker run --name official --network none --cpus 2 --memory 4g --pids-limit 512 auditgym`, then `docker cp` and `docker rm official` (the container is kept so that
  `runs/check/unittest.log` and `report.md` can be copied out, printed on failure and uploaded); then
  `tests.test_container` and `tests.test_redteam` inside the image, failing if any container test is skipped; then the
  check and `tests.test_container` again with `--user 10001` and with `--cap-drop ALL` (fallback to the host user); then, in default (non-strict) mode, a custom policy next to an answer key under `--cap-drop ALL`: inside `docker run --network none --cap-drop ALL` the step generates an episode into `/tmp`, runs `examples.custom_policy:FirstPagePolicy` on it and requires exit code 2, exactly one output line, starting with `error: custom policy` and naming `--allow-same-user`, and no output directory; then `python -m auditgym.redteam --parent` in three container modes (default image, `--user 10001`, `--cap-drop ALL`), each run preceded by an `echo` line `container mode: ...` so the log labels it;
  then strict mode (`-e AUDITGYM_REQUIRE_AGENT_USER=1`) in the default image, where the check must pass and no container
  test may be skipped, and with `--cap-drop ALL`, where the run must exit 2 with exactly one `error:` line; then the
  closed path as organizers run it: `check --seeds-file` with the example seeds file mounted read-only at
  `/app/secrets/closed.json`, the output directory mounted at `/app/runs/closed`, `--network none`, strict mode and
  the secret in `AUDITGYM_SECRET`; the step requires PASS and greps the output for answer-key issue IDs and the
  secret. The official-check, strict-mode and closed-path steps also fail unless the report written in the image carries the line
  `Policy isolation: separate user (uid N)`. The container logs and the closed-path output are uploaded as artifacts.

Latest run at the time of writing: run 45015789093, commit `5663020a830d2f3a9494633b377c4b11c15bb66b` (subject: `Cap d09 and d10 at the case's suggested sizes (at most 200 documents, 2000 ledger rows)`; code stamp `2b6130fb…`), conclusion success, all six jobs. The excerpt was made with `tools/ci_excerpt.py` from the full log (`gh run view 45015789093 --log`), which is not
committed. The lines cited here are kept in
[runs/ci/45015789093.txt](../runs/ci/45015789093.txt). The conclusion of every job and step is in [runs/ci/45015789093.jobs.json](../runs/ci/45015789093.jobs.json) (made from `gh run view --json jobs`, with URLs and IDs dropped). It also holds the start and end time of every job. The excerpt shows the container steps of the official check in the default image, of strict mode and of the closed path as organizers run it printing `Policy isolation: separate user (uid 10002).` (the `agent` user of the Dockerfile): the report written in the image says that the policy ran as a separate user. The committed `runs/check/report.md` is from a Windows host and says that the policy ran as the host's user; `runs/check_container/report.md` is the report that the official check wrote in the image in run 44944549237 (artifact `container-logs`, file `official_report.md`): `Policy isolation: separate user (uid 10002).`, Linux, Python 3.11.10, on the previous code (stamp `88d12bd7…`; the code of this cycle differs in `verify --regenerate` and in `configs/splits.json` (the capped d09 and d10), and the container jobs of run 45015789093 cover it).

The excerpt also keeps the step added in round 7e: under `--cap-drop ALL` in default mode, a custom policy on a
generated episode prints one line, `error: custom policy examples.custom_policy:FirstPagePolicy would run as the host's
user next to answer keys (/tmp/gen/grader): ...`, and the step reports `exit code 2`. Run 44913956128 on the round's first code commit `d32d7b9` failed in the container job only: the new spy test's temporary
directory was not readable by the image's policy uid; `c3205bc` opened it (as the redteam probe does) and changed nothing else.
The previous run, 44916932590 on `c3205bc55ed58a1effaddafdcfdb2debd44271c6` (round 8.2), was a success on all six jobs; its excerpt stays in [runs/ci/44916932590.txt](../runs/ci/44916932590.txt) and [runs/ci/44916932590.jobs.json](../runs/ci/44916932590.jobs.json). Before it, 44905020915 on `b78844c986b2e27d03c2cc5b496d75291c4a2270` (round 8.1), was a success on all six jobs; its excerpt stays in [runs/ci/44905020915.txt](../runs/ci/44905020915.txt)
and [runs/ci/44905020915.jobs.json](../runs/ci/44905020915.jobs.json). Before it, 44891150721 on `cd7794ba54b1170b8757857a097b67be8c14e19a` (round 8) was a success on all six jobs; its excerpt stays in [runs/ci/44891150721.txt](../runs/ci/44891150721.txt)
and [runs/ci/44891150721.jobs.json](../runs/ci/44891150721.jobs.json). Before it, 44859388346 on `9840b899d209b22251724f748a4e1e46efcf69d8` (round 7e.1) was a success on all six jobs; its excerpt stays in [runs/ci/44859388346.txt](../runs/ci/44859388346.txt)
and [runs/ci/44859388346.jobs.json](../runs/ci/44859388346.jobs.json). Before it, run 44841936613 on `b15fa6b67ca5c7731798730c357e5f1101953f80` (round 7e) was a success on all six jobs; its excerpt stays in [runs/ci/44841936613.txt](../runs/ci/44841936613.txt)
and [runs/ci/44841936613.jobs.json](../runs/ci/44841936613.jobs.json). Before it, run 44814588471 on commit
`c47af431f3a0da3ab5c0319a6226dbbe909a2b95` (round 7d) was a success on all six jobs; its excerpt stays in [runs/ci/44814588471.txt](../runs/ci/44814588471.txt) and
[runs/ci/44814588471.jobs.json](../runs/ci/44814588471.jobs.json). In round 7d, run 44811366128 on `56a11c6` had failed in the container
job only (one unit test expected the refusal advice of a host that cannot switch to the policy user), and `c47af43` fixed
that test. An earlier run on a code commit, 44775177143 on commit `03283bdbb73b2b8d04f89c3030ee8351d3d5cda1`, was a success on all six jobs; its excerpt stays
in [runs/ci/44775177143.txt](../runs/ci/44775177143.txt) and [runs/ci/44775177143.jobs.json](../runs/ci/44775177143.jobs.json). The
table and the skip counts below are from run 45015789093 (619 unit tests). The excerpt of the previous round's run, 44712065782 on commit `c9c7ab4`, stays in [runs/ci/44712065782.txt](../runs/ci/44712065782.txt).

| Job | Result | Unit tests (run, passed, skipped) | Time reported by the job |
|---|---|---|---|
| check (ubuntu-latest, Python 3.11) | success | 619, 596, 23 | `PASS in 167 s` |
| check (ubuntu-latest, Python 3.12) | success | 619, 596, 23 | `PASS in 205 s` |
| check (ubuntu-latest, Python 3.13) | success | 619, 596, 23 | `PASS in 150 s` |
| check (windows-latest, Python 3.11) | success | 619, 608, 11 | `PASS in 209 s` |
| check (macos-latest, Python 3.11) | success | 619, 593, 26 | `PASS in 253 s` |
| container (network none, 2 CPU, 4 GB) | success; image 240 MB | 619, 601, 18 | `PASS in 278 s`; `time` reports 279.7 s; `Policy isolation: separate user (uid 10002).`; the 9 tests in `tests/test_container.py` ran, none skipped |
| container, `--user 10001` | success | 619, 595, 24 | `PASS in 271 s`; the fallback warning line is printed; the 8 container-only tests are skipped |
| container, `--cap-drop ALL` | success | 619, 593, 26 | `PASS in 271 s`; the fallback warning line is printed; the 8 container-only tests are skipped |
| container, strict mode (`AUDITGYM_REQUIRE_AGENT_USER=1`) | success | 619, 601, 18 | `PASS in 282 s`; `Policy isolation: separate user (uid 10002).`; the 9 container tests `OK` |
| container, strict mode with `--cap-drop ALL` | success | not run | `exit code 2`, one `error:` line |
| container, custom policy next to an answer key under `--cap-drop ALL` (default mode) | success | not run | `exit code 2`, one `error: custom policy ...` line |
| container, closed path (mounted seeds file and output, strict) | success | not run | `PASS in 4 s`; `Policy isolation: separate user (uid 10002).`; `C_data 3/3 (1 skipped)`, `C_reward 49/49`, `D_paired 20/20`, `E_leaks 3/3`, `F_contract 20/20`, `B_replay 5/5` (101 named checks of 80 kinds) |

In run 45015789093, as in 44916932590 and 44905020915, every skip was platform-only or image-only: 8 container-only tests of `tests/test_container.py` outside the image and under `--user 10001` and `--cap-drop ALL`; 15 Windows-only tests off Windows (the Low-integrity child, parent-PID, report-line and secret-hygiene tests of `tests/test_windows_hardening.py` and `tests/test_redteam.py`); the 3 Linux-only hardening tests of `tests/test_linux_hardening.py` off Linux; the 2 negative hardening assertions when the test process runs as root (inside the image and under `--cap-drop ALL`); and the workflow-label test in `tests/test_linux_hardening.py`, which skips inside the image because `.dockerignore` leaves `.github` out. Per run: ubuntu 23 (the 8 container-only tests and the 15 Windows-only tests); Windows 11 (the 8 and the 3 Linux-only hardening tests); macOS 26 (the 8, the 15 and the 3); the default image 18 (the 15, the workflow-label test and the 2 negative assertions under root); `--user 10001` 24 (the 8, the 15 and the workflow-label test); `--cap-drop ALL` 26 (the 8, the 15, the workflow-label test and the 2 negative assertions under root).

The `redteam --parent` step prints, on ubuntu (3.11, 3.12 and 3.13), "host hardening: applied: PR_SET_DUMPABLE 0" and "same user as the host: the parent's environment is not readable"; on windows, "host hardening: Windows: no host-side hardening; the policy child lowers its own token to Low integrity", "same user as the host: child at Low integrity, the parent's environment is not readable (OpenProcess(PROCESS_VM_READ) error 5)" and "--secret-env: the parent's environment is not readable (OpenProcess(PROCESS_VM_READ) error 5)", while the control with the lowering off reads the variable ("child at the host's integrity level (off: control run), parent's environment readable, host variable found there"); on macOS, "same user as the host: not measured on this platform (no /proc)". In run 44712065782 (commit `c9c7ab4`, before the lowering) windows printed "same user as the host: parent's environment readable, host variable found there". The container job runs the same probe in three modes (the step "What a policy child sees of its parent in each container mode"). In the default image the parent's environment is not readable, also in the control with hardening off, because the separate uid blocks the read by itself. Under `--user 10001` and under `--cap-drop ALL` hardening is applied, the parent's environment is not readable, and the control with hardening off reads the variable ("host variable found there"). The `--secret-env` variable is not readable in any mode.

Python 3.12 and 3.13 run only the check job, on ubuntu. The job conclusion covers their byte-for-byte regeneration steps (`git diff --exit-code`), which the excerpt does not print. The container job runs the image's default command, which is
`python -m auditgym check`.

## 14. Open items at this version

- Blank or over-long IDs make a submission invalid, as documented (section 4).
- `runs/check/report.md` is a Windows 10 run (Python 3.11.4) with the code stamp `2b6130fb…`; its timings differ from the CI logs.
- Code gaps from the review of commit `849d0da` that are still open (the
  invoice count band, the sweep's invoice counts) are listed in [TASKS.md](TASKS.md).

Fixed earlier: the `journal_grouping` rule in `public/policy.json` now says the timestamps denote the same instant (commit `97c8f66`).
