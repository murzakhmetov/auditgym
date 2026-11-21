# Shortcut-tell measurement

Master string `auditgym-tells-v1`, 1000 generated episodes (750 with errors), 170318 public documents, 3799 affected documents (the answer key).
Reproduce: `python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells`.

A rule fires on the documents it selects. True hits are fired documents that are in the answer key; precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule fires at least once.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| ... and the payment is at most the invoice total | 1760 | 421 | 0.2392 | 0.1108 | 687 |
| receipt in the error window | 1023 | 209 | 0.2043 | 0.0550 | 621 |
| line-identical pair, earlier member paid | 2934 | 472 | 0.1609 | 0.1242 | 815 |
| sales invoice with a later line-identical repeat | 986 | 149 | 0.1511 | 0.0392 | 652 |
| residual: off-hours payment inside the error window | 1692 | 253 | 0.1495 | 0.0666 | 779 |
| invoice with a later line-identical repeat (2 to 10 days) | 1914 | 286 | 0.1494 | 0.0753 | 896 |
| later member of a line-identical pair | 1914 | 286 | 0.1494 | 0.0753 | 896 |
| purchase invoice with a later line-identical repeat | 928 | 137 | 0.1476 | 0.0361 | 628 |
| line-identical pair under 300 USD | 720 | 106 | 0.1472 | 0.0279 | 310 |
| paid twin invoice | 980 | 144 | 0.1469 | 0.0379 | 664 |
| line-identical pair in a foreign currency | 2860 | 416 | 0.1455 | 0.1095 | 792 |
| line-identical pair member posted off its issued_at | 1440 | 208 | 0.1444 | 0.0548 | 789 |
| sales invoice with a twin | 1880 | 264 | 0.1404 | 0.0695 | 640 |
| same-instant pair, terms != 30 or one copy paid | 3238 | 452 | 0.1396 | 0.1190 | 860 |
| invoice with a twin | 3860 | 534 | 0.1383 | 0.1406 | 921 |
| purchase invoice with a twin | 1980 | 270 | 0.1364 | 0.0711 | 673 |
| unpaid twin invoice | 2880 | 390 | 0.1354 | 0.1027 | 921 |
| same-instant pair with terms != 30 | 2566 | 344 | 0.1341 | 0.0906 | 766 |
| receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists | 1154 | 143 | 0.1239 | 0.0376 | 687 |
| payment with a 2900 row on an invoice that has no other payment | 3496 | 421 | 0.1204 | 0.1108 | 942 |
| receipt with invoice references and no 1100 row | 2667 | 289 | 0.1084 | 0.0761 | 852 |
| receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period | 4546 | 475 | 0.1045 | 0.1250 | 996 |
| lag across a date change on a foreign-currency document | 8496 | 794 | 0.0935 | 0.2090 | 999 |
| boundary day, off-hours payment | 3381 | 271 | 0.0802 | 0.0713 | 974 |
| receipt with a 2900 row on an opening-item invoice | 2333 | 177 | 0.0759 | 0.0466 | 934 |
| payment with a 2900 row and invoice refs | 10521 | 718 | 0.0682 | 0.1890 | 1000 |
| disbursement in the error window | 775 | 51 | 0.0658 | 0.0134 | 524 |
| lag equals the zone offset | 7786 | 447 | 0.0574 | 0.1177 | 898 |
| near-midnight (UTC date differs) payment | 7542 | 417 | 0.0553 | 0.1098 | 902 |
| posted later than its document | 12626 | 644 | 0.0510 | 0.1695 | 1000 |
| payment with a 2900 row | 14227 | 718 | 0.0505 | 0.1890 | 1000 |
| posting row at a different instant than its document | 29521 | 1390 | 0.0471 | 0.3659 | 1000 |
| sales invoice in the error window | 779 | 36 | 0.0462 | 0.0095 | 516 |
| purchase invoice in the error window | 769 | 35 | 0.0455 | 0.0092 | 513 |
| posted earlier than its document | 16895 | 746 | 0.0442 | 0.1964 | 1000 |
| within 12 h of period boundary | 10081 | 439 | 0.0435 | 0.1156 | 1000 |
| off-hours payment | 13501 | 506 | 0.0375 | 0.1332 | 1000 |
| residual: off-hours payment | 13501 | 506 | 0.0375 | 0.1332 | 1000 |
| a payment in a foreign currency | 31554 | 1107 | 0.0351 | 0.2914 | 1000 |
| near-midnight (UTC date differs) invoice | 7233 | 235 | 0.0325 | 0.0619 | 902 |
| off-hours document | 22425 | 719 | 0.0321 | 0.1893 | 1000 |
| sales invoice with two or more receipts that sum to less than its total | 3435 | 104 | 0.0303 | 0.0274 | 1000 |
| round amount | 2976 | 76 | 0.0255 | 0.0200 | 378 |
| off-hours invoice | 8924 | 213 | 0.0239 | 0.0561 | 1000 |
| a payment dated in another period (its timestamp is outside the reporting period) | 14664 | 348 | 0.0237 | 0.0916 | 1000 |
| terms 14 or 45 days | 61969 | 1439 | 0.0232 | 0.3788 | 1000 |
| terms not 30 days | 62432 | 1447 | 0.0232 | 0.3809 | 1000 |
| a disbursement | 13819 | 319 | 0.0231 | 0.0840 | 1000 |
| an invoice | 97783 | 2209 | 0.0226 | 0.5815 | 1000 |
| weekday date | 153073 | 3463 | 0.0226 | 0.9116 | 1000 |
| a receipt | 56377 | 1271 | 0.0225 | 0.3346 | 1000 |
| boundary day, off-hours invoice | 2851 | 64 | 0.0224 | 0.0168 | 958 |
| residual: off-hours payment outside the error window | 11809 | 253 | 0.0214 | 0.0666 | 1000 |
| top-3 foreign sale | 2999 | 62 | 0.0207 | 0.0163 | 1000 |
| weekend date | 17245 | 336 | 0.0195 | 0.0884 | 1000 |
| document on an FX holiday | 5873 | 106 | 0.0180 | 0.0279 | 682 |
| top-3 foreign purchase | 2992 | 46 | 0.0154 | 0.0121 | 1000 |
| largest foreign sale | 1000 | 13 | 0.0130 | 0.0034 | 1000 |
| largest invoice | 1000 | 13 | 0.0130 | 0.0034 | 1000 |
| a payment posted in another period (its rows are outside the reporting period) | 14490 | 174 | 0.0120 | 0.0458 | 1000 |
| lag of less than one hour | 2558 | 30 | 0.0117 | 0.0079 | 895 |
| largest foreign purchase | 1000 | 8 | 0.0080 | 0.0021 | 1000 |
| dominant foreign purchase (>= 1.5x runner-up) | 163 | 1 | 0.0061 | 0.0003 | 163 |
| qty/price outside catalogue | 0 | 0 | 0.0000 | 0.0000 | 0 |
| sales qty above catalogue max | 0 | 0 | 0.0000 | 0.0000 | 0 |
| same-instant pair of a subscription item | 0 | 0 | 0.0000 | 0.0000 | 0 |

## Episode-level rules

Base rate: 750 of 1000 episodes have errors (0.7500) and 250 are clean (0.2500). A rule is a tell only if its precision is well above the base rate of its label.

| rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| any quantity/price outside catalogue -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| any off-hours payment on a boundary day -> error | error | 974 | 734 | 0.7536 | 0.7500 |
| any same-instant pair with terms != 30 -> error | error | 766 | 566 | 0.7389 | 0.7500 |
| any posting at a different instant than its document -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| more postings at another instant than the size's largest default lag count -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| at most 5 documents posted later than their timestamp -> clean | clean | 90 | 38 | 0.4222 | 0.2500 |
| 8 or more ledger rows on account 2900 -> error | error | 988 | 746 | 0.7551 | 0.7500 |
| 2900 rows beyond twice the refunds plus the null-ref receipts -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| any receipt with a 2900 row lists an opening-item invoice -> error | error | 934 | 706 | 0.7559 | 0.7500 |
| any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error | error | 996 | 748 | 0.7510 | 0.7500 |
| any sales invoice with two or more receipts below its total -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| at most 3 sales invoices whose receipts sum above their total -> error | error | 44 | 28 | 0.6364 | 0.7500 |
| at most 0.64 payments per invoice -> error | error | 24 | 12 | 0.5000 | 0.7500 |
| 122 or more invoices -> error | error | 236 | 194 | 0.8220 | 0.7500 |
| every ledger timestamp in the local offset (no UTC, <= 2 offsets) -> clean | clean | 283 | 63 | 0.2226 | 0.2500 |
| small ledger (< 500 rows) with >= 2 refunds -> clean | clean | 203 | 62 | 0.3054 | 0.2500 |
| small ledger (< 500 rows) with >= 3 null-ref receipts -> clean | clean | 207 | 60 | 0.2899 | 0.2500 |

## Pair-count rules

The number of line-identical pairs of an episode is drawn per size and holds the duplicates, so it must not separate episodes with a duplicate from clean ones. The rules are measured here and in the generated-sample test only: the 20 committed episodes hold too few pairs per size.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| pair member in an episode with <= 2 line-identical pairs | 364 | 100 | 0.2747 | 0.0263 | 91 |

| episode rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| small ledger (< 500 rows) with >= 3 line-identical pairs -> error | error | 229 | 159 | 0.6943 | 0.7500 |

## Duplicates by side and shape

A line-identical pair is two invoices of one counterparty with the same kind, currency, total and lines (references ignored) at most 10 days apart. Its shape is `same` when both carry one instant and `later` when the second is keyed 2 to 9 days after the first. A pair is a duplicate when the answer key lists it. Decoys and duplicates come from one pair builder, so the precision of a pair is about the same in every cell.

| side/shape | pairs | duplicates | precision |
|---|---:|---:|---:|
| sales/same | 940 | 132 | 0.1404 |
| sales/later | 986 | 149 | 0.1511 |
| purchase/same | 990 | 135 | 0.1364 |
| purchase/later | 928 | 137 | 0.1476 |
| pooled | 3844 | 553 | 0.1439 |

## An error episode has a payment error

Of the 750 episodes with errors, 716 name a payment in the answer key (share 0.9547) and 576 name one in a wrong_fx_rate or wrong_period issue (share 0.7680); a policy that skips the payments loses those. Issues that name a payment, by type: unallocated_payment 718, wrong_fx_rate 500, wrong_period 522. This reads the answer key, so it is a statistic, not a shortcut rule on public features.

## FX target and the largest foreign purchase

Among the 66 episodes whose answer key has a wrong_fx_rate target that is a foreign purchase invoice, the largest foreign purchase is such a target in 5 (rate 0.0758). Chance level, the mean share of foreign purchases that are targets: 0.0975.

## Measured only in the regression test

The episode rules on the count of documents in the error window (more or fewer than the typical count, by size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents.
