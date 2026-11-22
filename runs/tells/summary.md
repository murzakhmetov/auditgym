# Shortcut-tell measurement

Master string `auditgym-tells-v1`, 1000 generated episodes (750 with errors), 158084 public documents, 3799 affected documents (the answer key).
Reproduce: `python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells`.

A rule fires on the documents it selects. True hits are fired documents that are in the answer key; precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule fires at least once.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| ... and the payment is at most the invoice total | 1763 | 424 | 0.2405 | 0.1116 | 688 |
| receipt in the error window | 1017 | 216 | 0.2124 | 0.0569 | 611 |
| residual: off-hours payment inside the error window | 1657 | 262 | 0.1581 | 0.0690 | 772 |
| line-identical pair, earlier member paid | 3002 | 460 | 0.1532 | 0.1211 | 820 |
| sales invoice with a later line-identical repeat | 979 | 147 | 0.1502 | 0.0387 | 648 |
| line-identical pair under 300 USD | 726 | 108 | 0.1488 | 0.0284 | 312 |
| invoice with a later line-identical repeat (2 to 10 days) | 1912 | 283 | 0.1480 | 0.0745 | 896 |
| later member of a line-identical pair | 1912 | 283 | 0.1480 | 0.0745 | 896 |
| line-identical pair in a foreign currency | 2842 | 420 | 0.1478 | 0.1106 | 793 |
| paid twin invoice | 973 | 143 | 0.1470 | 0.0376 | 662 |
| purchase invoice with a later line-identical repeat | 933 | 136 | 0.1458 | 0.0358 | 635 |
| sales invoice with a twin | 1860 | 268 | 0.1441 | 0.0705 | 636 |
| same-instant pair, terms != 30 or one copy paid | 3216 | 452 | 0.1405 | 0.1190 | 856 |
| invoice with a twin | 3864 | 540 | 0.1398 | 0.1421 | 919 |
| unpaid twin invoice | 2891 | 397 | 0.1373 | 0.1045 | 919 |
| purchase invoice with a twin | 2004 | 272 | 0.1357 | 0.0716 | 677 |
| line-identical pair member posted off its issued_at | 1514 | 205 | 0.1354 | 0.0540 | 799 |
| same-instant pair with terms != 30 | 2558 | 340 | 0.1329 | 0.0895 | 761 |
| receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists | 1161 | 145 | 0.1249 | 0.0382 | 692 |
| payment with a 2900 row on an invoice that has no other payment | 3501 | 424 | 0.1211 | 0.1116 | 938 |
| receipt with invoice references and no 1100 row | 2661 | 290 | 0.1090 | 0.0763 | 852 |
| receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period | 4552 | 470 | 0.1033 | 0.1237 | 994 |
| lag across a date change on a foreign-currency document | 8475 | 803 | 0.0947 | 0.2114 | 999 |
| boundary day, off-hours payment | 3290 | 275 | 0.0836 | 0.0724 | 971 |
| receipt with a 2900 row on an opening-item invoice | 2324 | 177 | 0.0762 | 0.0466 | 935 |
| disbursement in the error window | 743 | 54 | 0.0727 | 0.0142 | 502 |
| payment with a 2900 row and invoice refs | 10521 | 718 | 0.0682 | 0.1890 | 1000 |
| lag equals the zone offset | 7829 | 492 | 0.0628 | 0.1295 | 898 |
| near-midnight (UTC date differs) payment | 7176 | 411 | 0.0573 | 0.1082 | 902 |
| purchase invoice in the error window | 773 | 41 | 0.0530 | 0.0108 | 517 |
| posted later than its document | 12615 | 642 | 0.0509 | 0.1690 | 1000 |
| payment with a 2900 row | 14227 | 718 | 0.0505 | 0.1890 | 1000 |
| posting row at a different instant than its document | 29521 | 1422 | 0.0482 | 0.3743 | 1000 |
| within 12 h of period boundary | 9612 | 445 | 0.0463 | 0.1171 | 1000 |
| posted earlier than its document | 16906 | 780 | 0.0461 | 0.2053 | 1000 |
| sales invoice in the error window | 768 | 34 | 0.0443 | 0.0089 | 522 |
| off-hours payment | 12794 | 524 | 0.0410 | 0.1379 | 1000 |
| residual: off-hours payment | 12794 | 524 | 0.0410 | 0.1379 | 1000 |
| a payment in a foreign currency | 29399 | 1129 | 0.0384 | 0.2972 | 1000 |
| off-hours document | 21284 | 726 | 0.0341 | 0.1911 | 1000 |
| near-midnight (UTC date differs) invoice | 6905 | 229 | 0.0332 | 0.0603 | 902 |
| sales invoice with two or more receipts that sum to less than its total | 3429 | 98 | 0.0286 | 0.0258 | 1000 |
| a payment dated in another period (its timestamp is outside the reporting period) | 12871 | 356 | 0.0277 | 0.0937 | 1000 |
| round amount | 2742 | 71 | 0.0259 | 0.0187 | 371 |
| a disbursement | 12430 | 319 | 0.0257 | 0.0840 | 1000 |
| terms 14 or 45 days | 56947 | 1397 | 0.0245 | 0.3677 | 1000 |
| terms not 30 days | 57395 | 1405 | 0.0245 | 0.3698 | 1000 |
| an invoice | 90468 | 2209 | 0.0244 | 0.5815 | 1000 |
| top-3 foreign sale | 2999 | 73 | 0.0243 | 0.0192 | 1000 |
| weekday date | 141915 | 3455 | 0.0243 | 0.9094 | 1000 |
| a receipt | 52847 | 1271 | 0.0241 | 0.3346 | 1000 |
| off-hours invoice | 8490 | 202 | 0.0238 | 0.0532 | 1000 |
| residual: off-hours payment outside the error window | 11137 | 262 | 0.0235 | 0.0690 | 1000 |
| boundary day, off-hours invoice | 2847 | 66 | 0.0232 | 0.0174 | 961 |
| weekend date | 16169 | 344 | 0.0213 | 0.0906 | 1000 |
| document on an FX holiday | 5455 | 115 | 0.0211 | 0.0303 | 679 |
| largest foreign sale | 1000 | 21 | 0.0210 | 0.0055 | 1000 |
| largest invoice | 1000 | 15 | 0.0150 | 0.0039 | 1000 |
| top-3 foreign purchase | 2991 | 44 | 0.0147 | 0.0116 | 1000 |
| a payment posted in another period (its rows are outside the reporting period) | 12681 | 166 | 0.0131 | 0.0437 | 1000 |
| lag of less than one hour | 2554 | 29 | 0.0114 | 0.0076 | 895 |
| largest foreign purchase | 1000 | 7 | 0.0070 | 0.0018 | 1000 |
| dominant foreign purchase (>= 1.5x runner-up) | 174 | 1 | 0.0057 | 0.0003 | 174 |
| qty/price outside catalogue | 0 | 0 | 0.0000 | 0.0000 | 0 |
| sales qty above catalogue max | 0 | 0 | 0.0000 | 0.0000 | 0 |
| same-instant pair of a subscription item | 0 | 0 | 0.0000 | 0.0000 | 0 |

## Episode-level rules

Base rate: 750 of 1000 episodes have errors (0.7500) and 250 are clean (0.2500). A rule is a tell only if its precision is well above the base rate of its label.

| rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| any quantity/price outside catalogue -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| any off-hours payment on a boundary day -> error | error | 971 | 731 | 0.7528 | 0.7500 |
| any same-instant pair with terms != 30 -> error | error | 761 | 564 | 0.7411 | 0.7500 |
| any posting at a different instant than its document -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| more postings at another instant than the size's largest default lag count -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| at most 5 documents posted later than their timestamp -> clean | clean | 90 | 38 | 0.4222 | 0.2500 |
| 8 or more ledger rows on account 2900 -> error | error | 988 | 746 | 0.7551 | 0.7500 |
| 2900 rows beyond twice the refunds plus the null-ref receipts -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| any receipt with a 2900 row lists an opening-item invoice -> error | error | 935 | 708 | 0.7572 | 0.7500 |
| any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error | error | 994 | 746 | 0.7505 | 0.7500 |
| any sales invoice with two or more receipts below its total -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| at most 3 sales invoices whose receipts sum above their total -> error | error | 44 | 28 | 0.6364 | 0.7500 |
| at most 0.64 payments per invoice -> error | error | 22 | 10 | 0.4545 | 0.7500 |
| 122 or more invoices -> error | error | 0 | 0 | 0.0000 | 0.7500 |
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
| sales/same | 930 | 134 | 0.1441 |
| sales/later | 979 | 147 | 0.1502 |
| purchase/same | 1002 | 136 | 0.1357 |
| purchase/later | 933 | 136 | 0.1458 |
| pooled | 3844 | 553 | 0.1439 |

## An error episode has a payment error

Of the 750 episodes with errors, 716 name a payment in the answer key (share 0.9547) and 576 name one in a wrong_fx_rate or wrong_period issue (share 0.7680); a policy that skips the payments loses those. Issues that name a payment, by type: unallocated_payment 718, wrong_fx_rate 500, wrong_period 522. This reads the answer key, so it is a statistic, not a shortcut rule on public features.

## FX target and the largest foreign purchase

Among the 62 episodes whose answer key has a wrong_fx_rate target that is a foreign purchase invoice, the largest foreign purchase is such a target in 4 (rate 0.0645). Chance level, the mean share of foreign purchases that are targets: 0.1047.

## Measured only in the regression test

The episode rules on the count of documents in the error window (more or fewer than the typical count, by size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents.
