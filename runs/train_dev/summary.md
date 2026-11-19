| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9466 | 0.9466 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 26.7 | 0.022 | 1.0 | 0.962 | 0.9427 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -0.9892 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.006 | 3.0 | 0.0032 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 33.4 | 0.0094 | 0.0 | -1.0 | -1.0 | 4 | 0.0 |
| dev | recon | 10 | -0.5449 | -0.5449 | 0.1835 | 0.4733 | 0.1739 | 0.6667 | 0.2481 | 0.2481 | 26.7 | 0.0079 | 0.0 | -1.0 | -0.4311 | 16 | 0.0 |
| train | auditor | 10 | 0.9698 | 0.9698 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 15.1 | 0.008 | 1.0 | 0.9713 | 0.9691 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0048 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 21.5 | 0.0048 | 0.0 | -1.0 | -1.0 | 5 | 0.0 |
| train | recon | 10 | -0.6375 | -0.6375 | 0.1176 | 0.5 | 0.12 | 0.6 | 0.1883 | 0.1883 | 15.1 | 0.0062 | 0.0 | -1.0 | -0.4822 | 11 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | amount=2, search=28 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=0.4444, wrong_period=0.375 | not_flagged=10 |
| train | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=0.6667, wrong_period=0.25 | not_flagged=4 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| dev | auditor | 0.9466 | 0.9466 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -0.9892 | 0.0108 | 0.0 | 0.006 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | recon | -0.5449 | -0.5449 | 0.0 | 0.2481 | 0.2481 |
| train | auditor | 0.9698 | 0.9698 | 0.0 | 1.0 | 1.0 |
| train | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| train | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | recon | -0.6375 | -0.6375 | 0.0 | 0.1883 | 0.1883 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| dev | auditor | 0 | - | 19.2667 | 0 / 30 (0.0) | 0 / 120 |
| dev | flag_all | 300 | boundary_doc=5, legit_repeat=9, midnight_fx=10, multi_invoice_payment=14, near_issue=12, overpayment_refund=4, recurring=40, underpayment=6, unrelated=200 | - | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 120 / 120 |
| dev | random | 17 | multi_invoice_payment=2, near_issue=1, overpayment_refund=2, split_payment=5, underpayment=1, unrelated=6 | - | 0 / 30 (0.0) | 0 / 59 |
| dev | recon | 95 | boundary_doc=8, legit_repeat=24, midnight_fx=7, multi_invoice_payment=2, near_issue=1, overpayment_refund=14, recurring=5, split_payment=2, underpayment=2, unrelated=30 | 19.2667 | 10 / 30 (0.3333) | 0 / 501 |
| train | auditor | 0 | - | 12.4 | 0 / 10 (0.0) | 0 / 35 |
| train | flag_all | 300 | boundary_doc=10, legit_repeat=10, midnight_fx=1, multi_invoice_payment=19, recurring=34, split_payment=10, underpayment=1, unrelated=215 | - | 0 / 10 (0.0) | 0 / 190 |
| train | oracle | 0 | - | - | - | 35 / 35 |
| train | random | 12 | recurring=2, unrelated=10 | - | 0 / 10 (0.0) | 0 / 47 |
| train | recon | 44 | boundary_doc=3, legit_repeat=13, midnight_fx=7, null_ref_receipt=1, overpayment_refund=11, recurring=2, twin_legit_repeat=1, unrelated=6 | 12.4 | 4 / 10 (0.4) | 0 / 233 |
