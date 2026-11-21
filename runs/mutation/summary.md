# Mutation smoke

**181 of 181 listed mutants killed** (0 survived, 0 equivalent, not counted).

Recorded on Windows, Python 3.11. `policy-path-append` is killed only by a test that runs on Windows, so it runs only there.

133 of 181 are killed by the test modules listed for them. The other 48 pass those modules and are killed by `tests/test_mutation_survivors.py`, which was written for these mutants; the remaining test modules are not run against a mutant.

Each mutant is one hand-written change to the core (`auditgym/__main__.py`, `auditgym/agent.py`, `auditgym/auditor.py`, `auditgym/books.py`, `auditgym/check.py`, `auditgym/check_battery.py`, `auditgym/config.py`, `auditgym/env.py`, `auditgym/evidence_check.py`, `auditgym/grader.py`, `auditgym/history.py`, `auditgym/inject.py`, `auditgym/matcher.py`, `auditgym/policy.py`, `auditgym/protocol.py`, `auditgym/reward.py`, `auditgym/schemas.py`, `auditgym/tells.py`, `auditgym/transform.py`, `auditgym/verify.py`), applied to a fresh copy of the repository, which then runs the unit-test modules named in the last column, and, if those pass, `tests/test_mutation_survivors.py`. A mutant is killed when those tests fail. The list is in `tools/mutation_smoke.py`; this file holds no timings.

Regenerate: `python tools/mutation_smoke.py OUT_DIR --record`.

| # | mutant | file | what it breaks | result | killed by | tests run |
|---|---|---|---|---|---|---|
| 1 | `matcher-type` | `auditgym/matcher.py` | criterion type: a finding of another type still matches | killed | listed tests | test_matcher, test_reward, test_env |
| 2 | `matcher-ids-subset` | `auditgym/matcher.py` | criterion affected_ids: a subset of the key's IDs matches | killed | listed tests | test_matcher, test_reward, test_env |
| 3 | `matcher-currency` | `auditgym/matcher.py` | criterion currency: a wrong currency still matches | killed | listed tests | test_matcher, test_reward, test_env |
| 4 | `matcher-amount-boundary` | `auditgym/matcher.py` | criterion amount: the tolerance boundary is exclusive | killed | listed tests | test_matcher, test_reward, test_env |
| 5 | `matcher-amount-one-sided` | `auditgym/matcher.py` | criterion amount: an under-claim of any size matches | killed | survivor tests | test_matcher, test_reward, test_env |
| 6 | `matcher-amount-no-tolerance` | `auditgym/matcher.py` | criterion amount: the per-issue tolerance is ignored | killed | listed tests | test_matcher, test_reward, test_env |
| 7 | `matcher-evidence-overlap` | `auditgym/matcher.py` | criterion evidence: a partial overlap with an evidence set is enough | killed | listed tests | test_matcher, test_reward, test_env |
| 8 | `matcher-evidence-all-sets` | `auditgym/matcher.py` | criterion evidence: every acceptable set must be cited, not one | killed | listed tests | test_matcher, test_reward, test_env |
| 9 | `matcher-currency-case` | `auditgym/matcher.py` | normalization: the finding's currency is no longer upper-cased | killed | listed tests | test_matcher, test_reward, test_env |
| 10 | `matcher-id-strip` | `auditgym/matcher.py` | normalization: IDs keep surrounding whitespace | killed | listed tests | test_matcher, test_reward, test_env |
| 11 | `matcher-alias-affected` | `auditgym/matcher.py` | alias: a doc_id in affected_ids is no longer mapped to its invoice_id/payment_id | killed | survivor tests | test_matcher, test_reward, test_env |
| 12 | `matcher-alias-evidence` | `auditgym/matcher.py` | alias: an invoice_id/payment_id in evidence_ids is no longer mapped to its doc_id | killed | survivor tests | test_matcher, test_reward, test_env |
| 13 | `matcher-one-to-one` | `auditgym/matcher.py` | maximum matching: a later finding takes an issue from an earlier one, which is not re-matched | killed | listed tests | test_matcher, test_reward, test_env |
| 14 | `matcher-tp-counts-edges` | `auditgym/matcher.py` | one-to-one: every finding with a candidate issue is a true positive, so one issue can score several times | killed | listed tests | test_matcher, test_reward, test_env |
| 15 | `matcher-no-augmenting-path` | `auditgym/matcher.py` | maximum matching: greedy first-fit instead of augmenting paths | killed | listed tests | test_matcher, test_reward, test_env |
| 16 | `matcher-tiebreak-order` | `auditgym/matcher.py` | tie-break: issues are tried in descending issue_id order | killed | survivor tests | test_matcher, test_reward, test_env |
| 17 | `matcher-repeat-not-fp` | `auditgym/matcher.py` | false positives: an exact repeat of a matched finding is no longer counted | killed | listed tests | test_matcher, test_reward, test_env |
| 18 | `matcher-f1-formula` | `auditgym/matcher.py` | F1: false negatives dropped from the denominator | killed | listed tests | test_matcher, test_reward, test_env |
| 19 | `matcher-f1-empty` | `auditgym/matcher.py` | F1: an empty answer on a clean ledger scores 0, not 1 | killed | listed tests | test_matcher, test_reward, test_env |
| 20 | `matcher-precision-empty` | `auditgym/matcher.py` | precision with no findings is 1.0, not 0.0 | killed | listed tests | test_matcher, test_reward, test_env |
| 21 | `reward-step-cost-value` | `auditgym/reward.py` | step cost is 0.003 per inspection step instead of 0.002 | killed | listed tests | test_reward, test_matcher, test_env |
| 22 | `reward-step-cost-dropped` | `auditgym/reward.py` | step cost: inspection steps are free | killed | listed tests | test_reward, test_matcher, test_env |
| 23 | `reward-f1-scale` | `auditgym/reward.py` | reward: F1 is not mapped to [-1, 1] | killed | listed tests | test_reward, test_matcher, test_env |
| 24 | `reward-clip-lower` | `auditgym/reward.py` | clip: no lower bound, so many steps push the reward below -1 | killed | listed tests | test_reward, test_matcher, test_env |
| 25 | `reward-clip-upper` | `auditgym/reward.py` | clip helper: no upper bound (not reachable through the reward: every caller passes a value <= 1) | killed | survivor tests | test_reward, test_matcher, test_env |
| 26 | `reward-invalid-constant` | `auditgym/reward.py` | an invalid submission is not rewarded -1 | killed | listed tests | test_reward, test_matcher, test_env |
| 27 | `reward-soft-denominator` | `auditgym/reward.py` | experimental reward: extra findings no longer lower soft F1 | killed | listed tests | test_reward, test_matcher, test_env |
| 28 | `reward-soft-empty` | `auditgym/reward.py` | experimental reward: an empty answer on a clean ledger scores 0, not 1 | killed | survivor tests | test_reward, test_matcher, test_env |
| 29 | `reward-soft-credit-scale` | `auditgym/reward.py` | experimental reward: credit is not in quarters | killed | listed tests | test_reward, test_matcher, test_env |
| 30 | `reward-soft-amount-credit` | `auditgym/reward.py` | experimental reward: amount credit needs only the currency or only the amount | killed | survivor tests | test_reward, test_matcher, test_env |
| 31 | `reward-soft-group-key` | `auditgym/reward.py` | experimental reward: findings compete for issues of the same type with other IDs | killed | survivor tests | test_reward, test_matcher, test_env |
| 32 | `reward-assignment-positive` | `auditgym/reward.py` | assignment helper: zero-weight pairs are reported (not reachable through experimental_reward: weights are >= 2) | killed | survivor tests | test_reward, test_matcher, test_env |
| 33 | `grader-closed` | `auditgym/grader.py` | closed: a run with only false positives or only misses counts as closed | killed | survivor tests | test_matcher, test_reward, test_env |
| 34 | `grader-invalid-fn` | `auditgym/grader.py` | invalid submission: no issue counts as missed | killed | survivor tests | test_matcher, test_reward, test_env |
| 35 | `grader-invalid-reward` | `auditgym/grader.py` | invalid submission: the grade's reward is not -1 | killed | listed tests | test_matcher, test_reward, test_env |
| 36 | `grader-steps-in-reward` | `auditgym/grader.py` | grade: the step cost is not applied | killed | listed tests | test_matcher, test_reward, test_env |
| 37 | `grader-aliases` | `auditgym/grader.py` | grade: the answer key's id_aliases are not used | killed | survivor tests | test_matcher, test_reward, test_env |
| 38 | `grader-error-cap` | `auditgym/grader.py` | invalid submission: the error list is capped at 21, not 20 | killed | survivor tests | test_matcher, test_reward, test_env |
| 39 | `grader-missed-issues` | `auditgym/grader.py` | grade: missed issues are not listed | killed | survivor tests | test_matcher, test_reward, test_env |
| 40 | `schemas-findings-count` | `auditgym/schemas.py` | limit: 30 findings are already too many | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 41 | `schemas-evidence-count` | `auditgym/schemas.py` | limit: 11 evidence IDs are accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 42 | `schemas-affected-count` | `auditgym/schemas.py` | limit: 11 affected IDs are accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 43 | `schemas-id-length` | `auditgym/schemas.py` | limit: an ID of exactly 64 characters is too long | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 44 | `schemas-explanation-length` | `auditgym/schemas.py` | limit: an explanation of exactly 1000 characters is too long | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 45 | `schemas-amount-upper` | `auditgym/schemas.py` | limit: the maximum amount itself is rejected | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 46 | `schemas-amount-lower` | `auditgym/schemas.py` | limit: an amount of 0 is rejected | killed | survivor tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 47 | `schemas-surrogate-id` | `auditgym/schemas.py` | lone surrogate in an ID is accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 48 | `schemas-surrogate-explanation` | `auditgym/schemas.py` | lone surrogate in an explanation is accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 49 | `schemas-surrogate-episode-id` | `auditgym/schemas.py` | lone surrogate in the episode_id is accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 50 | `schemas-bool-amount` | `auditgym/schemas.py` | True is accepted as an integer amount | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 51 | `schemas-affected-min` | `auditgym/schemas.py` | an empty affected_ids list is accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 52 | `schemas-blank-id` | `auditgym/schemas.py` | a blank ID is accepted | killed | survivor tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 53 | `schemas-currency-shape` | `auditgym/schemas.py` | a 2-letter currency is accepted | killed | survivor tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 54 | `schemas-episode-mismatch` | `auditgym/schemas.py` | a submission for another episode is accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 55 | `schemas-unknown-finding-keys` | `auditgym/schemas.py` | unknown keys inside a finding are accepted | killed | listed tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 56 | `schemas-coerce-int` | `auditgym/schemas.py` | a fractional float amount is truncated to an integer | killed | survivor tests | test_schemas, test_contract_battery, test_env, test_matcher |
| 57 | `schemas-page-size` | `auditgym/schemas.py` | page size is 51 instead of 50 | killed | listed tests | test_env, test_contract_battery |
| 58 | `env-page-limit` | `auditgym/env.py` | page size: limit 51 is accepted | killed | listed tests | test_env, test_contract_battery |
| 59 | `env-page-default` | `auditgym/env.py` | page size: the default page is 10 rows, not 50 | killed | listed tests | test_env, test_contract_battery |
| 60 | `env-step-budget` | `auditgym/env.py` | step budget: one extra step is allowed before truncation | killed | listed tests | test_env, test_contract_battery |
| 61 | `env-max-steps-bound` | `auditgym/env.py` | step budget: the default maximum of 100 is rejected | killed | listed tests | test_env, test_contract_battery |
| 62 | `env-cursor-end` | `auditgym/env.py` | cursor: the end-of-table offset is a bad cursor | killed | survivor tests | test_env, test_contract_battery |
| 63 | `env-next-cursor` | `auditgym/env.py` | cursor: the last page announces another page | killed | listed tests | test_env, test_contract_battery |
| 64 | `env-eval-hides-reward` | `auditgym/env.py` | eval mode: the terminal reward reaches the policy | killed | listed tests | test_env, test_contract_battery |
| 65 | `env-eval-hides-info` | `auditgym/env.py` | eval mode: TP/FP/FN and the reward reach the policy in info | killed | listed tests | test_env, test_contract_battery |
| 66 | `env-inspection-steps` | `auditgym/env.py` | step cost: the final submit counts as an inspection step | killed | listed tests | test_env, test_contract_battery |
| 67 | `env-rows-copy` | `auditgym/env.py` | isolation: the policy receives the environment's own row objects | killed | survivor tests | test_env, test_contract_battery |
| 68 | `env-time-limit` | `auditgym/env.py` | time limit: the boundary instant already truncates | killed | survivor tests | test_env, test_contract_battery |
| 69 | `env-finished-noop` | `auditgym/env.py` | a finished episode accepts more actions | killed | listed tests | test_env, test_contract_battery |
| 70 | `env-submit-extra-keys` | `auditgym/env.py` | a submit with unknown action keys is accepted | killed | survivor tests | test_env, test_contract_battery |
| 71 | `verify-colon-in-id` | `auditgym/verify.py` | ids_unique: a ':' inside an ID is allowed | killed | survivor tests | test_verify, test_generator |
| 72 | `verify-duplicate-id` | `auditgym/verify.py` | ids_unique: one ID used in two tables is allowed | killed | survivor tests | test_verify, test_generator |
| 73 | `verify-record-counts` | `auditgym/verify.py` | records_schema: a wrong manifest record count passes | killed | survivor tests | test_verify, test_generator |
| 74 | `verify-amount-mismatch` | `auditgym/verify.py` | declared_discrepancies: an auditor/key amount mismatch passes | killed | survivor tests | test_verify, test_generator |
| 75 | `verify-evidence-sets` | `auditgym/verify.py` | declared_discrepancies: differing evidence sets pass | killed | listed tests | test_verify, test_generator |
| 76 | `verify-unknown-variant` | `auditgym/verify.py` | declared_discrepancies: an unknown issue variant passes | killed | listed tests | test_verify, test_generator |
| 77 | `verify-budget-bound` | `auditgym/verify.py` | budget_feasible: the submit step is not counted | killed | survivor tests | test_verify, test_generator |
| 78 | `verify-surface-pattern` | `auditgym/verify.py` | no_surface_tells: a touched ledger row with a unique pattern passes | killed | survivor tests | test_verify, test_generator |
| 79 | `verify-leak-marker` | `auditgym/verify.py` | no_leaks: the word provenance is no longer a leak marker | killed | survivor tests | test_verify, test_generator |
| 80 | `verify-final-digest` | `auditgym/verify.py` | provenance_roundtrip: a public digest that differs from final_digest passes | killed | listed tests | test_verify, test_generator |
| 81 | `verify-clean-digest` | `auditgym/verify.py` | provenance_roundtrip: reverted tables with the wrong clean digest pass | killed | listed tests | test_verify, test_generator |
| 82 | `verify-op-touches` | `auditgym/verify.py` | provenance_roundtrip: an issue with no op touching its records passes | killed | listed tests | test_verify, test_generator |
| 83 | `verify-injection-match` | `auditgym/verify.py` | provenance_roundtrip: injections and truth issues may differ | killed | listed tests | test_verify, test_generator |
| 84 | `verify-retarget` | `auditgym/verify.py` | provenance_roundtrip: an injection retargeted to other records passes | killed | listed tests | test_verify, test_generator |
| 85 | `evidence-fx-tolerance` | `auditgym/evidence_check.py` | wrong_fx_rate: a difference exactly at the tolerance counts as an error | killed | survivor tests | test_verify, test_generator |
| 86 | `evidence-uncited-record` | `auditgym/evidence_check.py` | evidence IDs that name no record are ignored | killed | survivor tests | test_verify, test_generator |
| 87 | `evidence-duplicate-account` | `auditgym/evidence_check.py` | duplicate_invoice: rows in different accounts still support it | killed | survivor tests | test_verify, test_generator |
| 88 | `evidence-duplicate-signature` | `auditgym/evidence_check.py` | duplicate_invoice: two different invoices still support it | killed | survivor tests | test_verify, test_generator |
| 89 | `evidence-duplicate-own-posting` | `auditgym/evidence_check.py` | duplicate_invoice: a row of a payment (a relief), not the invoice's own posting, still supports it | killed | survivor tests | test_verify, test_generator |
| 90 | `evidence-duplicate-posting-account` | `auditgym/evidence_check.py` | duplicate_invoice: two rows in an account the invoice kind does not post to still support it | killed | survivor tests | test_verify, test_generator |
| 91 | `evidence-duplicate-row-period` | `auditgym/evidence_check.py` | duplicate_invoice: a row booked in another period than its invoice still supports it | killed | survivor tests | test_verify, test_generator |
| 92 | `evidence-duplicate-row-instant-required` | `auditgym/evidence_check.py` | duplicate_invoice: a row posted at another moment of its invoice's period no longer supports it (a posting lag breaks the evidence) | killed | listed tests | test_posting_lag |
| 93 | `evidence-duplicate-equal-amounts` | `auditgym/evidence_check.py` | duplicate_invoice: two copies of one instant that post different amounts still support it | killed | survivor tests | test_verify, test_generator |
| 94 | `evidence-duplicate-signature-issued-at` | `auditgym/evidence_check.py` | duplicate_invoice: issued_at is part of the signature again, so a copy keyed again later no longer supports it | killed | listed tests | test_verify, test_generator |
| 95 | `evidence-duplicate-later-amount` | `auditgym/evidence_check.py` | duplicate_invoice: the amount is the earlier document's row, not the later copy's | killed | listed tests | test_verify, test_generator |
| 96 | `evidence-duplicate-rekey-clause` | `auditgym/evidence_check.py` | duplicate_invoice: a later copy supports the finding although the published rule does not say issued_at may differ | killed | survivor tests | test_verify, test_generator |
| 97 | `auditor-duplicate-earlier-amount` | `auditgym/auditor.py` | duplicate_invoice: the independent auditor takes the amount of the earlier copy, not the later one | killed | listed tests | test_verify, test_generator |
| 98 | `auditor-duplicate-signature-issued-at` | `auditgym/auditor.py` | duplicate_invoice: the independent auditor needs one instant again, so it misses a copy keyed again later | killed | listed tests | test_verify, test_generator |
| 99 | `config-repeat-pairs-plus-duplicates` | `auditgym/config.py` | pairs: the visible pair count grows with the number of duplicates | killed | listed tests | test_generator |
| 100 | `config-repeat-pairs-crowded-out` | `auditgym/config.py` | pairs: a duplicate count above the range leaves no decoy pair, every visible pair is a duplicate | killed | listed tests | test_generator |
| 101 | `tells-pair-group-exactly-two` | `auditgym/tells.py` | pairs: an ordinary invoice of the same price hides a repeat pair from the tells | killed | listed tests | test_tells |
| 102 | `cli-same-user-fallback-unrecorded` | `auditgym/__main__.py` | allow_same_user: a closed run that fell back to the host user is recorded as not having used the override | killed | listed tests | test_cli |
| 103 | `inject-duplicate-copy-keeps-original-instant` | `auditgym/inject.py` | duplicate_invoice: a re-keyed copy takes the original's instant, so the variant is never later | killed | listed tests | test_generator |
| 104 | `inject-duplicate-copy-keeps-own-refs` | `auditgym/inject.py` | duplicate_invoice: the copy keeps its own fresh references, so the pair is two separate supplies | killed | listed tests | test_generator |
| 105 | `history-pair-one-shape` | `auditgym/history.py` | pairs: every decoy pair carries one instant, so a pair keyed again later is always a duplicate | killed | listed tests | test_generator |
| 106 | `policy-posting-moment` | `auditgym/policy.py` | policy: the published rule says again that a posting's timestamp equals its document's, which the data no longer follow | killed | listed tests | test_posting_lag |
| 107 | `books-lag-ignored` | `auditgym/books.py` | posting lag: an invoice's lag is dropped when it is booked, so the shape recorded in provenance is not in the ledger | killed | listed tests | test_posting_lag |
| 108 | `history-lag-crosses-period` | `auditgym/history.py` | posting lag: a lag may carry a posting past the end of its document's period | killed | listed tests | test_posting_lag |
| 109 | `history-lag-order` | `auditgym/history.py` | posting lag: a payment may be booked before the invoice it settles, which changes the allocation | killed | listed tests | test_posting_lag |
| 110 | `history-lag-date-change-same-rate` | `auditgym/history.py` | posting lag: a lag across a date change may land on a date with the same rate, so it is no hard negative for wrong_fx_rate | killed | listed tests | test_posting_lag |
| 111 | `history-lag-utc-sign` | `auditgym/history.py` | posting lag: the UTC wall-clock shape moves the posting the wrong way, so it no longer mirrors utc_wall_clock | killed | listed tests | test_posting_lag |
| 112 | `history-lag-error-documents` | `auditgym/history.py` | posting lag: documents of error issues never take one, so a lag marks a document clean | killed | listed tests | test_posting_lag |
| 113 | `history-lag-pair-documents` | `auditgym/history.py` | posting lag: members of line-identical pairs never take one, so a pair member posted at another moment is a duplicate | killed | listed tests | test_tells, test_posting_lag |
| 114 | `history-lag-budget-ignores-errors` | `auditgym/history.py` | posting lag: the lags of ordinary documents come on top of the postings that are errors, so an error episode shows more of them | killed | listed tests | test_posting_lag |
| 115 | `history-lag-protected-documents` | `auditgym/history.py` | posting lag: a document whose posting is the error (wrong_period, posting_date, the boundary receipt) may take a lag as well | killed | listed tests | test_posting_lag |
| 116 | `history-lag-sibling-payments` | `auditgym/history.py` | posting lag: payments of one invoice may swap their posting order, which moves an allocation | killed | listed tests | test_posting_lag |
| 117 | `history-lag-taken-instants` | `auditgym/history.py` | posting lag: a lagged posting may share its instant with another document | killed | listed tests | test_posting_lag |
| 118 | `history-lag-shortfall-silent` | `auditgym/history.py` | posting lag: an explicit count that cannot be placed is lowered without a word | killed | listed tests | test_posting_lag |
| 119 | `config-lag-range-on-main-stream` | `auditgym/config.py` | config: the lag count is drawn on the main stream, which moves every draw after it | killed | listed tests | test_posting_lag |
| 120 | `auditor-lag-anomaly` | `auditgym/auditor.py` | auditor: a posting at another moment inside the period is an anomaly again, so a clean book with lags fails | killed | listed tests | test_posting_lag, test_verify |
| 121 | `tells-lag-offset-sign` | `auditgym/tells.py` | tells: the rule 'lag equals the zone offset' has the wrong sign, so it misses the UTC wall-clock lags | killed | listed tests | test_posting_lag |
| 122 | `battery-posting-lag-attack` | `auditgym/check_battery.py` | check battery: a posting lag has no false accusation, so the distractor goes unchecked | killed | listed tests | test_check_battery |
| 123 | `evidence-unallocated-total` | `auditgym/evidence_check.py` | unallocated_payment: a payment equal to the invoice total is rejected | killed | listed tests | test_verify, test_generator |
| 124 | `evidence-unallocated-account` | `auditgym/evidence_check.py` | unallocated_payment: every cited row is taken for the 2900 row, so no true set derives | killed | listed tests | test_verify, test_generator |
| 125 | `evidence-unallocated-booked-after` | `auditgym/evidence_check.py` | unallocated_payment: an invoice booked after the receipt still counts as open when the receipt arrived | killed | survivor tests | test_verify, test_generator |
| 126 | `evidence-unallocated-other-relief` | `auditgym/evidence_check.py` | unallocated_payment: a relief by another receipt among the cited rows still supports it | killed | listed tests | test_verify, test_generator |
| 127 | `evidence-unallocated-open-balance` | `auditgym/evidence_check.py` | unallocated_payment: an invoice the relief fully settled still counts as open | killed | listed tests | test_verify, test_generator |
| 128 | `evidence-unallocated-relief-bound` | `auditgym/evidence_check.py` | unallocated_payment: the relief may exceed what the receipt paid | killed | listed tests | test_verify, test_generator |
| 129 | `evidence-unallocated-base-identity` | `auditgym/evidence_check.py` | unallocated_payment: in the base currency the cited balance need not cover the receipt, nor equal relief plus 2900 | killed | listed tests | test_verify, test_generator |
| 130 | `evidence-unallocated-base-cover` | `auditgym/evidence_check.py` | unallocated_payment: in the base currency a posting below the receipt still supports it | killed | listed tests | test_verify, test_generator |
| 131 | `evidence-unallocated-bank-count` | `auditgym/evidence_check.py` | unallocated_payment: a foreign-currency set without its bank row (or a base set with one) still supports it | killed | listed tests | test_verify, test_generator |
| 132 | `evidence-unallocated-bank-split` | `auditgym/evidence_check.py` | unallocated_payment: in a foreign currency the 2900 amount need not split the bank amount | killed | listed tests | test_verify, test_generator |
| 133 | `verify-complete-evidence-set` | `auditgym/verify.py` | evidence_sufficient: an unallocated_payment set may omit a receivable row of the invoice | killed | listed tests | test_verify, test_generator |
| 134 | `verify-complete-bank-row` | `auditgym/verify.py` | evidence_sufficient: a foreign-currency unallocated_payment set may omit the payment's bank row | killed | listed tests | test_verify, test_generator |
| 135 | `evidence-unallocated-prior-late` | `auditgym/evidence_check.py` | unallocated_payment: a relief booked after the receipt still counts as an earlier part payment | killed | listed tests | test_credit_receipts, test_verify |
| 136 | `evidence-unallocated-complete-rows` | `auditgym/evidence_check.py` | unallocated_payment: a set that leaves out the relief of an earlier part payment (and so shows a larger balance) derives the finding | killed | listed tests | test_credit_receipts, test_verify |
| 137 | `verify-sole-receipt-late` | `auditgym/verify.py` | evidence_sufficient: another payment on the invoice booked after the receipt passes as an earlier part payment | killed | listed tests | test_credit_receipts |
| 138 | `verify-alloc-prior-relief` | `auditgym/verify.py` | change record: the relief of an unallocated receipt on a part-paid invoice is checked against the whole carrying amount | killed | listed tests | test_credit_receipts, test_generator |
| 139 | `inject-part-paid-never` | `auditgym/inject.py` | unallocated_payment: every error target is the only payment of its invoice, so a payment count marks the answer key | killed | listed tests | test_credit_receipts |
| 140 | `config-credit-total-ignores-errors` | `auditgym/config.py` | config: the prepaid receipts come on top of the unallocated_payment errors, so the rows on 2900 grow with the errors | killed | listed tests | test_credit_receipts |
| 141 | `history-credit-receipts-none` | `auditgym/history.py` | distractors: no receipt leaves a credit in 2900 without an error, so a single payment with a 2900 row is always one | killed | listed tests | test_credit_receipts |
| 142 | `history-credit-prepaid-never` | `auditgym/history.py` | distractors: no receipt precedes its invoice, so a single receipt within the total with a 2900 row is always an error | killed | listed tests | test_credit_receipts |
| 143 | `history-credit-topped-up-never` | `auditgym/history.py` | distractors: no receipt that relieves the rest of a part-paid invoice also credits an excess, so a 1100 and a 2900 row on an invoice with two receipts is always an error | killed | listed tests | test_credit_receipts |
| 144 | `config-invoice-load-ignored` | `auditgym/config.py` | config: the invoices an error adds come on top of the drawn counts, so the invoice count grows with the errors | killed | listed tests | test_credit_receipts |
| 145 | `history-open-invoice-never-prior` | `auditgym/history.py` | distractors: no credit receipt and no unallocated receipt is on an opening item, or the other way round: a 2900 credit on an opening item is an error | killed | listed tests | test_credit_receipts |
| 146 | `inject-unallocated-prior-flags-ignored` | `auditgym/inject.py` | unallocated_payment: the opening items an error brings are not the ones taken out of the prior invoices, so their number grows with the errors | killed | listed tests | test_credit_receipts |
| 147 | `config-prior-hits-not-deducted` | `auditgym/config.py` | config: the opening items of the unallocated receipts come on top of the prior invoices, so the opening items grow with the errors | killed | listed tests | test_credit_receipts |
| 148 | `history-split-remainder-none` | `auditgym/history.py` | distractors: no invoice has two receipts that leave a rest open, so such an invoice is always a part-paid unallocated_payment error | killed | listed tests | test_credit_receipts |
| 149 | `history-paid-slots-ignore-load` | `auditgym/history.py` | history: the invoices an error adds are never paid and come out of the count, so the payments per invoice fall with the errors | killed | listed tests | test_credit_receipts |
| 150 | `history-credit-dates-business-days` | `auditgym/history.py` | distractors: every 2900 credit that is not prepaid sits on an invoice of the first days of the period, so a later invoice is an error | killed | listed tests | test_credit_receipts |
| 151 | `history-credit-second-share-fixed` | `auditgym/history.py` | distractors: the share of credits that follow an earlier receipt is the same in every episode | killed | listed tests | test_credit_receipts |
| 152 | `config-prepaid-always-drawn` | `auditgym/config.py` | config: every episode has prepaid receipts, so an episode without a receipt dated before its invoice is one with unallocated errors | killed | listed tests | test_credit_receipts |
| 153 | `history-split-remainder-never-prior` | `auditgym/history.py` | distractors: a part-paid invoice that leaves a rest is never an opening item, so such an opening item is an error | killed | listed tests | test_credit_receipts |
| 154 | `evidence-fx-future-date` | `auditgym/evidence_check.py` | wrong_fx_rate: a rate dated on the document's own day is rejected | killed | listed tests | test_verify, test_generator |
| 155 | `evidence-period-boundary` | `auditgym/evidence_check.py` | wrong_period: the period end instant belongs to the period | killed | survivor tests | test_verify, test_generator |
| 156 | `evidence-offset-start` | `auditgym/evidence_check.py` | local date: the UTC offset change takes effect one instant late | killed | survivor tests | test_verify, test_generator |
| 157 | `evidence-half-even` | `auditgym/evidence_check.py` | rounding: half_even always rounds the tie up | killed | listed tests | test_verify, test_generator |
| 158 | `protocol-max-line` | `auditgym/protocol.py` | bound: a line of exactly MAX_LINE characters is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 159 | `protocol-max-depth` | `auditgym/protocol.py` | bound: nesting of exactly MAX_DEPTH is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 160 | `protocol-max-nodes` | `auditgym/protocol.py` | bound: exactly MAX_NODES parsed nodes is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 161 | `protocol-separator-count` | `auditgym/protocol.py` | bound: commas are not counted against the node limit | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 162 | `protocol-max-digits` | `auditgym/protocol.py` | bound: an integer literal of exactly MAX_NUMBER_CHARS digits is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 163 | `protocol-max-float` | `auditgym/protocol.py` | bound: a float literal of exactly MAX_FLOAT_CHARS characters is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 164 | `protocol-nonsubmit-size` | `auditgym/protocol.py` | bound: a non-submit line of exactly 2048 characters is malformed | killed | survivor tests | test_isolation, test_redteam, test_contract_fuzz |
| 165 | `protocol-nan` | `auditgym/protocol.py` | NaN and Infinity are accepted as numbers | killed | listed tests | test_isolation, test_redteam, test_contract_fuzz |
| 166 | `protocol-echo-length` | `auditgym/protocol.py` | echo: a malformed line is echoed 257 characters long | killed | listed tests | test_isolation, test_redteam, test_contract_fuzz |
| 167 | `protocol-surrogate` | `auditgym/protocol.py` | a lone surrogate in an action is accepted | killed | listed tests | test_isolation, test_redteam, test_contract_fuzz |
| 168 | `verify-stale-rate-variant` | `auditgym/verify.py` | provenance: the stale_rate change.wrong_rate_date is not checked against the fx.csv rate | killed | listed tests | test_verify, test_generator |
| 169 | `shift-direction-order` | `auditgym/transform.py` | shift_direction tries -28 before +28 | killed | listed tests | test_transform_shift |
| 170 | `config-boundary-utc-date-positive` | `auditgym/config.py` | boundary_fx_payment: a positive offset takes utc_date even when the first day after the period is a weekend (both dates then take one rate and the error has no amount) | killed | listed tests | test_generator |
| 171 | `inject-boundary-fallback` | `auditgym/inject.py` | boundary_fx_payment: a boundary that gives utc_date no amount still gets a utc_date error | killed | listed tests | test_generator |
| 172 | `config-boundary-fallback-refusal` | `auditgym/config.py` | boundary_fx_payment: a fixed month without a utc_date amount is refused although stale_rate or transposed is allowed | killed | listed tests | test_generator |
| 173 | `check-shift-direction-order` | `auditgym/check.py` | D_paired tries the -28 shift before +28 | killed | listed tests | test_transform_shift |
| 174 | `shift-period-lower` | `auditgym/transform.py` | shift: a period landing exactly on 2000 is refused | killed | listed tests | test_transform_shift |
| 175 | `policy-path-append` | `auditgym/agent.py` | Windows child: the policy directory goes last on sys.path, not after the staged code | killed | listed tests | test_windows_hardening, test_redteam, test_isolation |
| 176 | `cli-keys-refusal` | `auditgym/__main__.py` | a custom policy next to an answer key outside the open splits is neither refused nor warned about | killed | listed tests | test_cli |
| 177 | `cli-keys-fallback-unarmed` | `auditgym/__main__.py` | a custom policy next to an answer key falls back to the host's user at the fallback point with only a warning | killed | listed tests | test_cli |
| 178 | `protocol-cap-setuid` | `auditgym/protocol.py` | a root without CAP_SETUID counts as able to switch to the policy user | killed | listed tests | test_cli |
| 179 | `check-no-secret-refusal` | `auditgym/check.py` | check --seeds-file without a secret and without --no-secret runs | killed | listed tests | test_cli |
| 180 | `env-weak-seed-bound` | `auditgym/env.py` | eval mode accepts a seed of exactly 40 bits without a secret | killed | listed tests | test_env, test_contract_battery |
| 181 | `inject-utc-wall-clock-dst` | `auditgym/inject.py` | a standalone utc_wall_clock error can post inside the DST window of the boundary night (New York, October 2026) | killed | listed tests | test_generator |
