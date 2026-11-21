# Shortcut-tell measurement

Master string `auditgym-tells-v1`, 1000 generated episodes (750 with errors), 170770 public documents, 3799 affected documents (the answer key).
Reproduce: `python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells`.

A rule fires on the documents it selects. True hits are fired documents that are in the answer key; precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule fires at least once.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| ... and the payment is at most the invoice total | 1862 | 434 | 0.2331 | 0.1142 | 666 |
| receipt in the error window | 1035 | 211 | 0.2039 | 0.0555 | 647 |
| paid twin invoice | 991 | 152 | 0.1534 | 0.0400 | 655 |
| residual: off-hours payment inside the error window | 1675 | 255 | 0.1522 | 0.0671 | 790 |
| purchase invoice with a later line-identical repeat | 1015 | 150 | 0.1478 | 0.0395 | 672 |
| line-identical pair, earlier member paid | 2932 | 432 | 0.1473 | 0.1137 | 824 |
| purchase invoice with a twin | 1926 | 280 | 0.1454 | 0.0737 | 651 |
| same-instant pair, terms != 30 or one copy paid | 3192 | 460 | 0.1441 | 0.1211 | 838 |
| invoice with a twin | 3852 | 554 | 0.1438 | 0.1458 | 899 |
| invoice with a later line-identical repeat (2 to 10 days) | 1920 | 276 | 0.1437 | 0.0727 | 929 |
| later member of a line-identical pair | 1920 | 276 | 0.1437 | 0.0727 | 929 |
| line-identical pair under 300 USD | 672 | 96 | 0.1429 | 0.0253 | 290 |
| sales invoice with a twin | 1926 | 274 | 0.1423 | 0.0721 | 646 |
| same-instant pair with terms != 30 | 2514 | 356 | 0.1416 | 0.0937 | 757 |
| line-identical pair in a foreign currency | 2920 | 412 | 0.1411 | 0.1084 | 806 |
| unpaid twin invoice | 2861 | 402 | 0.1405 | 0.1058 | 899 |
| sales invoice with a later line-identical repeat | 905 | 126 | 0.1392 | 0.0332 | 631 |
| line-identical pair member posted off its issued_at | 1360 | 181 | 0.1331 | 0.0476 | 719 |
| payment with a 2900 row on an invoice that has no other payment | 3653 | 434 | 0.1188 | 0.1142 | 941 |
| receipt with a 1100 row and a 2900 row on an invoice that another receipt also lists | 1215 | 140 | 0.1152 | 0.0369 | 711 |
| receipt with a 2900 row dated after its invoice, the invoice not issued on days 0 to 10 of the period | 4666 | 473 | 0.1014 | 0.1245 | 997 |
| receipt with invoice references and no 1100 row | 2721 | 267 | 0.0981 | 0.0703 | 849 |
| lag across a date change on a foreign-currency document | 8854 | 781 | 0.0882 | 0.2056 | 998 |
| receipt with a 2900 row on an opening-item invoice | 2342 | 198 | 0.0845 | 0.0521 | 928 |
| boundary day, off-hours payment | 3454 | 274 | 0.0793 | 0.0721 | 981 |
| payment with a 2900 row and invoice refs | 10562 | 718 | 0.0680 | 0.1890 | 1000 |
| disbursement in the error window | 753 | 51 | 0.0677 | 0.0134 | 531 |
| lag equals the zone offset | 6481 | 409 | 0.0631 | 0.1077 | 901 |
| near-midnight (UTC date differs) payment | 7537 | 431 | 0.0572 | 0.1135 | 905 |
| payment with a 2900 row | 14206 | 718 | 0.0505 | 0.1890 | 1000 |
| posted earlier than its document | 16240 | 759 | 0.0467 | 0.1998 | 1000 |
| posting row at a different instant than its document | 29398 | 1356 | 0.0461 | 0.3569 | 1000 |
| posted later than its document | 13158 | 597 | 0.0454 | 0.1571 | 999 |
| within 12 h of period boundary | 10257 | 421 | 0.0410 | 0.1108 | 1000 |
| purchase invoice in the error window | 733 | 29 | 0.0396 | 0.0076 | 515 |
| off-hours payment | 13602 | 525 | 0.0386 | 0.1382 | 1000 |
| residual: off-hours payment | 13602 | 525 | 0.0386 | 0.1382 | 1000 |
| a payment in a foreign currency | 31690 | 1110 | 0.0350 | 0.2922 | 1000 |
| sales invoice in the error window | 777 | 27 | 0.0347 | 0.0071 | 542 |
| off-hours document | 22533 | 776 | 0.0344 | 0.2043 | 1000 |
| near-midnight (UTC date differs) invoice | 7184 | 218 | 0.0303 | 0.0574 | 905 |
| dominant foreign purchase (>= 1.5x runner-up) | 203 | 6 | 0.0296 | 0.0016 | 203 |
| sales invoice with two or more receipts that sum to less than its total | 3436 | 99 | 0.0288 | 0.0261 | 1000 |
| off-hours invoice | 8931 | 251 | 0.0281 | 0.0661 | 1000 |
| largest foreign sale | 1000 | 26 | 0.0260 | 0.0068 | 1000 |
| a payment dated in another period (its timestamp is outside the reporting period) | 14863 | 376 | 0.0253 | 0.0990 | 1000 |
| round amount | 2831 | 70 | 0.0247 | 0.0184 | 384 |
| a disbursement | 13946 | 331 | 0.0237 | 0.0871 | 1000 |
| terms 14 or 45 days | 62391 | 1441 | 0.0231 | 0.3793 | 1000 |
| terms not 30 days | 62681 | 1450 | 0.0231 | 0.3817 | 1000 |
| residual: off-hours payment outside the error window | 11927 | 270 | 0.0226 | 0.0711 | 1000 |
| a receipt | 56586 | 1274 | 0.0225 | 0.3354 | 1000 |
| an invoice | 97976 | 2194 | 0.0224 | 0.5775 | 1000 |
| weekday date | 153347 | 3427 | 0.0223 | 0.9021 | 1000 |
| document on an FX holiday | 5992 | 133 | 0.0222 | 0.0350 | 677 |
| top-3 foreign sale | 3000 | 65 | 0.0217 | 0.0171 | 1000 |
| weekend date | 17423 | 372 | 0.0214 | 0.0979 | 1000 |
| boundary day, off-hours invoice | 2863 | 58 | 0.0203 | 0.0153 | 965 |
| top-3 foreign purchase | 2979 | 56 | 0.0188 | 0.0147 | 999 |
| largest foreign purchase | 999 | 15 | 0.0150 | 0.0039 | 999 |
| largest invoice | 1000 | 14 | 0.0140 | 0.0037 | 1000 |
| lag of less than one hour | 2664 | 37 | 0.0139 | 0.0097 | 897 |
| a payment posted in another period (its rows are outside the reporting period) | 14654 | 167 | 0.0114 | 0.0440 | 1000 |
| qty/price outside catalogue | 0 | 0 | 0.0000 | 0.0000 | 0 |
| sales qty above catalogue max | 0 | 0 | 0.0000 | 0.0000 | 0 |
| same-instant pair of a subscription item | 0 | 0 | 0.0000 | 0.0000 | 0 |

## Episode-level rules

Base rate: 750 of 1000 episodes have errors (0.7500) and 250 are clean (0.2500). A rule is a tell only if its precision is well above the base rate of its label.

| rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| any quantity/price outside catalogue -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| any off-hours payment on a boundary day -> error | error | 981 | 740 | 0.7543 | 0.7500 |
| any same-instant pair with terms != 30 -> error | error | 757 | 573 | 0.7569 | 0.7500 |
| any posting at a different instant than its document -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| more postings at another instant than the size's largest default lag count -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| at most 5 documents posted later than their timestamp -> clean | clean | 69 | 21 | 0.3043 | 0.2500 |
| 8 or more ledger rows on account 2900 -> error | error | 978 | 737 | 0.7536 | 0.7500 |
| 2900 rows beyond twice the refunds plus the null-ref receipts -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| any receipt with a 2900 row lists an opening-item invoice -> error | error | 928 | 701 | 0.7554 | 0.7500 |
| any receipt with a 2900 row dated after an invoice not issued on days 0 to 10 -> error | error | 997 | 748 | 0.7503 | 0.7500 |
| any sales invoice with two or more receipts below its total -> error | error | 1000 | 750 | 0.7500 | 0.7500 |
| at most 3 sales invoices whose receipts sum above their total -> error | error | 45 | 31 | 0.6889 | 0.7500 |
| at most 0.64 payments per invoice -> error | error | 18 | 14 | 0.7778 | 0.7500 |
| 122 or more invoices -> error | error | 255 | 214 | 0.8392 | 0.7500 |
| every ledger timestamp in the local offset (no UTC, <= 2 offsets) -> clean | clean | 292 | 68 | 0.2329 | 0.2500 |
| small ledger (< 500 rows) with >= 2 refunds -> clean | clean | 202 | 62 | 0.3069 | 0.2500 |
| small ledger (< 500 rows) with >= 3 null-ref receipts -> clean | clean | 207 | 66 | 0.3188 | 0.2500 |

## Pair-count rules

The number of line-identical pairs of an episode is drawn per size and holds the duplicates, so it must not separate episodes with a duplicate from clean ones. The rules are measured here and in the generated-sample test only: the 20 committed episodes hold too few pairs per size.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| pair member in an episode with <= 2 line-identical pairs | 408 | 116 | 0.2843 | 0.0305 | 102 |

| episode rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| small ledger (< 500 rows) with >= 3 line-identical pairs -> error | error | 218 | 147 | 0.6743 | 0.7500 |

## Duplicates by side and shape

A line-identical pair is two invoices of one counterparty with the same kind, currency, total and lines (references ignored) at most 10 days apart. Its shape is `same` when both carry one instant and `later` when the second is keyed 2 to 9 days after the first. A pair is a duplicate when the answer key lists it. Decoys and duplicates come from one pair builder, so the precision of a pair is about the same in every cell.

| side/shape | pairs | duplicates | precision |
|---|---:|---:|---:|
| sales/same | 963 | 137 | 0.1423 |
| sales/later | 905 | 126 | 0.1392 |
| purchase/same | 963 | 140 | 0.1454 |
| purchase/later | 1015 | 150 | 0.1478 |
| pooled | 3846 | 553 | 0.1438 |

## An error episode has a payment error

Of the 750 episodes with errors, 717 name a payment in the answer key (share 0.9560) and 574 name one in a wrong_fx_rate or wrong_period issue (share 0.7653); a policy that skips the payments loses those. Issues that name a payment, by type: unallocated_payment 718, wrong_fx_rate 494, wrong_period 543. This reads the answer key, so it is a statistic, not a shortcut rule on public features.

## FX target and the largest foreign purchase

Among the 64 episodes whose answer key has a wrong_fx_rate target that is a foreign purchase invoice, the largest foreign purchase is such a target in 7 (rate 0.1094). Chance level, the mean share of foreign purchases that are targets: 0.0983.

## Measured only in the regression test

The episode rules on the count of documents in the error window (more or fewer than the typical count, by size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents.
