# Shortcut-tell measurement

Master string `auditgym-tells-v1`, 1000 generated episodes (750 with errors), 170058 public documents, 3799 affected documents (the answer key).
Reproduce: `python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells`.

A rule fires on the documents it selects. True hits are fired documents that are in the answer key; precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule fires at least once.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| ... and the payment is at most the invoice total | 1885 | 435 | 0.2308 | 0.1145 | 686 |
| sales invoice with a twin | 1798 | 290 | 0.1613 | 0.0763 | 636 |
| same-instant pair, terms != 30 or one copy paid | 3140 | 488 | 0.1554 | 0.1285 | 846 |
| same-instant pair with terms != 30 | 2516 | 390 | 0.1550 | 0.1027 | 770 |
| line-identical pair, earlier member paid | 2774 | 424 | 0.1528 | 0.1116 | 807 |
| paid twin invoice | 922 | 140 | 0.1518 | 0.0369 | 637 |
| line-identical pair in a foreign currency | 2860 | 430 | 0.1503 | 0.1132 | 804 |
| purchase invoice with a later line-identical repeat | 906 | 136 | 0.1501 | 0.0358 | 641 |
| receipt in the error window | 1009 | 150 | 0.1487 | 0.0395 | 616 |
| invoice with a twin | 3786 | 562 | 0.1484 | 0.1479 | 912 |
| unpaid twin invoice | 2864 | 422 | 0.1473 | 0.1111 | 912 |
| invoice with a later line-identical repeat (2 to 10 days) | 1883 | 272 | 0.1445 | 0.0716 | 911 |
| later member of a line-identical pair | 1883 | 272 | 0.1445 | 0.0716 | 911 |
| sales invoice with a later line-identical repeat | 977 | 136 | 0.1392 | 0.0358 | 657 |
| purchase invoice with a twin | 1988 | 272 | 0.1368 | 0.0716 | 671 |
| line-identical pair member posted off its issued_at | 1304 | 172 | 0.1319 | 0.0453 | 731 |
| line-identical pair under 300 USD | 686 | 84 | 0.1224 | 0.0221 | 295 |
| payment with a 2900 row on an invoice that has no other payment | 3594 | 435 | 0.1210 | 0.1145 | 946 |
| receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists | 1155 | 133 | 0.1152 | 0.0350 | 697 |
| purchase invoice in the error window | 883 | 96 | 0.1087 | 0.0253 | 582 |
| receipt with invoice references and no 1100 row | 2771 | 292 | 0.1054 | 0.0769 | 869 |
| receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period | 4512 | 460 | 0.1020 | 0.1211 | 999 |
| sales invoice in the error window | 831 | 82 | 0.0987 | 0.0216 | 550 |
| residual: off-hours payment inside the error window | 1611 | 138 | 0.0857 | 0.0363 | 756 |
| lag across a date change on a foreign-currency document | 8253 | 706 | 0.0855 | 0.1858 | 998 |
| receipt with a 2900 row on an opening-item invoice | 2289 | 187 | 0.0817 | 0.0492 | 917 |
| payment with a 2900 row and invoice refs | 10436 | 718 | 0.0688 | 0.1890 | 1000 |
| near-midnight (UTC date differs) invoice | 7712 | 472 | 0.0612 | 0.1242 | 921 |
| boundary day, off-hours invoice | 2975 | 175 | 0.0588 | 0.0461 | 970 |
| lag equals the zone offset | 7949 | 437 | 0.0550 | 0.1150 | 920 |
| payment with a 2900 row | 14080 | 718 | 0.0510 | 0.1890 | 1000 |
| off-hours invoice | 9137 | 458 | 0.0501 | 0.1206 | 1000 |
| posted earlier than its document | 16876 | 779 | 0.0462 | 0.2051 | 1000 |
| posting row at a different instant than its document | 29236 | 1348 | 0.0461 | 0.3548 | 1000 |
| posted later than its document | 12360 | 569 | 0.0460 | 0.1498 | 1000 |
| largest foreign sale | 1000 | 44 | 0.0440 | 0.0116 | 1000 |
| boundary day, off-hours payment | 3296 | 143 | 0.0434 | 0.0376 | 965 |
| within 12 h of period boundary | 10143 | 430 | 0.0424 | 0.1132 | 1000 |
| top-3 foreign sale | 3000 | 115 | 0.0383 | 0.0303 | 1000 |
| top-3 foreign purchase | 2985 | 111 | 0.0372 | 0.0292 | 999 |
| largest invoice | 1000 | 36 | 0.0360 | 0.0095 | 1000 |
| terms 14 or 45 days | 61914 | 1976 | 0.0319 | 0.5201 | 1000 |
| terms not 30 days | 62374 | 1990 | 0.0319 | 0.5238 | 1000 |
| off-hours document | 22557 | 699 | 0.0310 | 0.1840 | 1000 |
| near-midnight (UTC date differs) payment | 7646 | 209 | 0.0273 | 0.0550 | 920 |
| sales invoice with two or more receipts that sum to less than its total | 3424 | 92 | 0.0269 | 0.0242 | 1000 |
| weekday date | 152757 | 3429 | 0.0224 | 0.9026 | 1000 |
| document on an FX holiday | 6026 | 131 | 0.0217 | 0.0345 | 691 |
| weekend date | 17301 | 370 | 0.0214 | 0.0974 | 1000 |
| dominant foreign purchase (>= 1.5x runner-up) | 190 | 4 | 0.0211 | 0.0011 | 190 |
| largest foreign purchase | 999 | 20 | 0.0200 | 0.0053 | 999 |
| off-hours payment | 13420 | 241 | 0.0180 | 0.0634 | 1000 |
| residual: off-hours payment | 13420 | 241 | 0.0180 | 0.0634 | 1000 |
| round amount | 2765 | 47 | 0.0170 | 0.0124 | 385 |
| lag of less than one hour | 2424 | 34 | 0.0140 | 0.0089 | 881 |
| residual: off-hours payment outside the error window | 11809 | 103 | 0.0087 | 0.0271 | 1000 |
| disbursement in the error window | 722 | 0 | 0.0000 | 0.0000 | 509 |
| qty/price outside catalogue | 0 | 0 | 0.0000 | 0.0000 | 0 |
| sales qty above catalogue max | 0 | 0 | 0.0000 | 0.0000 | 0 |
| same-instant pair of a subscription item | 0 | 0 | 0.0000 | 0.0000 | 0 |

## Episode-level rules

Base rate: 750 of 1000 episodes have errors (0.7500) and 250 are clean (0.2500). A rule is a tell only if its precision is well above the base rate of its label.

| rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| any quantity/price outside catalogue -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| any off-hours payment on a boundary day -> error | error | 965 | 723 | 0.7492 | 0.7500 |
| any same-instant pair with terms != 30 -> error | error | 770 | 582 | 0.7558 | 0.7500 |
| any posting at a different instant than its document -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| more postings at another instant than the size's largest default lag count -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| at most 5 documents posted later than their timestamp -> clean | clean | 97 | 24 | 0.2474 | 0.2500 |
| 8 or more ledger rows on account 2900 -> error | error | 985 | 742 | 0.7533 | 0.7500 |
| 2900 rows beyond twice the refunds plus the null-ref receipts -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| any receipt with a 2900 row lists an opening-item invoice -> error | error | 917 | 689 | 0.7514 | 0.7500 |
| any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error | error | 999 | 749 | 0.7497 | 0.7500 |
| any sales invoice with two or more receipts below its total -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| at most 3 sales invoices whose receipts sum above their total -> error | error | 53 | 35 | 0.6604 | 0.7500 |
| at most 0.64 payments per invoice -> error | error | 18 | 12 | 0.6667 | 0.7500 |
| 122 or more invoices -> error | error | 240 | 207 | 0.8625 | 0.7500 |
| every ledger timestamp in the local offset (no UTC, <= 2 offsets) -> clean | clean | 306 | 79 | 0.2582 | 0.2500 |
| small ledger (< 500 rows) with >= 2 refunds -> clean | clean | 206 | 61 | 0.2961 | 0.2500 |
| small ledger (< 500 rows) with >= 3 null-ref receipts -> clean | clean | 207 | 71 | 0.3430 | 0.2500 |

## Pair-count rules

The number of line-identical pairs of an episode is drawn per size and holds the duplicates, so it must not separate episodes with a duplicate from clean ones. The rules are measured here and in the generated-sample test only: the 20 committed episodes hold too few pairs per size.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| pair member in an episode with <= 2 line-identical pairs | 484 | 122 | 0.2521 | 0.0321 | 121 |

| episode rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| small ledger (< 500 rows) with >= 3 line-identical pairs -> error | error | 199 | 138 | 0.6935 | 0.7500 |

## Duplicates by side and shape

A line-identical pair is two invoices of one counterparty with the same kind, currency, total and lines (references ignored) at most 10 days apart. Its shape is `same` when both carry one instant and `later` when the second is keyed 2 to 9 days after the first. A pair is a duplicate when the answer key lists it. Decoys and duplicates come from one pair builder, so the precision of a pair is about the same in every cell.

| side/shape | pairs | duplicates | precision |
|---|---:|---:|---:|
| sales/same | 899 | 145 | 0.1613 |
| sales/later | 977 | 136 | 0.1392 |
| purchase/same | 994 | 136 | 0.1368 |
| purchase/later | 906 | 136 | 0.1501 |
| pooled | 3776 | 553 | 0.1465 |

## FX target and the largest foreign purchase

Among the 181 episodes whose answer key has a wrong_fx_rate target that is a foreign purchase invoice, the largest foreign purchase is such a target in 17 (rate 0.0939). Chance level, the mean share of foreign purchases that are targets: 0.1057.

## Measured only in the regression test

The episode rules on the count of documents in the error window (more or fewer than the typical count, by size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents.
