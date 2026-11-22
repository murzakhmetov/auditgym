| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.942 | 0.942 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 29.0 | 0.0135 | 1.0 | 0.959 | 0.9378 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0022 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 24.1 | 0.0035 | 0.0 | -1.0 | -1.0 | 5 | 0.0 |
| dev | recon | 10 | -0.7121 | -0.7121 | 0.1082 | 0.515 | 0.1124 | 0.6667 | 0.1667 | 0.1667 | 29.0 | 0.0091 | 0.0 | -1.0 | -0.6401 | 14 | 0.0 |
| dev | silent | 10 | -0.6 | -0.6 | 0.0 | 0.0 | n/a | 0.0 | 0.2 | 0.2 | 0.0 | 0.0002 | 0.2 | 1.0 | -1.0 | 0 | n/a |
| train | auditor | 10 | 0.969 | 0.969 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 15.5 | 0.0083 | 1.0 | 0.9747 | 0.9666 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0028 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 29.7 | 0.0056 | 0.0 | -1.0 | -1.0 | 7 | 0.0 |
| train | recon | 10 | -0.7247 | -0.7247 | 0.0848 | 0.6 | 0.0777 | 0.8 | 0.1479 | 0.1479 | 15.5 | 0.0052 | 0.0 | -1.0 | -0.6067 | 36 | 0.0 |
| train | silent | 10 | -0.4 | -0.4 | 0.0 | 0.0 | n/a | 0.0 | 0.3 | 0.3 | 0.0 | 0.0002 | 0.3 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | recon | duplicate_invoice=0.3333, unallocated_payment=1.0, wrong_fx_rate=0.6667, wrong_period=0.625 | not_flagged=10 |
| dev | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| train | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | not_flagged=1, search=9 |
| train | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=0.5 | not_flagged=2 |
| train | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| dev | auditor | 0.942 | 0.942 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | recon | -0.7121 | -0.7121 | 0.0 | 0.1667 | 0.1667 |
| dev | silent | -0.6 | -0.6 | 0.0 | 0.2 | 0.2 |
| train | auditor | 0.969 | 0.969 | 0.0 | 1.0 | 1.0 |
| train | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| train | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | recon | -0.7247 | -0.7247 | 0.0 | 0.1479 | 0.1479 |
| train | silent | -0.4 | -0.4 | 0.0 | 0.3 | 0.3 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| dev | auditor | 0 | - | 27.4333 | 0 / 30 (0.0) | 0 / 137 |
| dev | flag_all | 300 | boundary_doc=1, credit_receipt=27, legit_repeat=5, midnight_fx=6, near_issue=7, overpayment_refund=20, posting_lag=4, recurring=67, split_payment=11, unrelated=151, weekend_fx=1 | - | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 137 / 137 |
| dev | random | 10 | credit_receipt=1, multi_invoice_payment=1, unrelated=8 | - | 0 / 30 (0.0) | 0 / 25 |
| dev | recon | 158 | boundary_doc=14, credit_receipt=61, legit_repeat=8, midnight_fx=12, near_issue=2, overpayment_refund=25, posting_lag=2, recurring=5, split_payment=3, unrelated=26 | 27.4333 | 10 / 30 (0.3333) | 0 / 970 |
| dev | silent | 0 | - | - | 0 / 30 (0.0) | 0 / 0 |
| train | auditor | 0 | - | 13.5 | 0 / 10 (0.0) | 0 / 39 |
| train | flag_all | 300 | boundary_doc=31, credit_receipt=20, legit_repeat=15, midnight_fx=10, multi_invoice_payment=10, near_issue=4, overpayment_refund=21, posting_lag=26, recurring=22, split_payment=30, underpayment=4, unrelated=100, weekend_fx=7 | 3.0 | 1 / 10 (0.1) | 0 / 190 |
| train | oracle | 0 | - | - | - | 39 / 39 |
| train | random | 18 | credit_receipt=1, legit_repeat=1, overpayment_refund=1, split_payment=4, underpayment=1, unrelated=10 | - | 0 / 10 (0.0) | 0 / 56 |
| train | recon | 95 | boundary_doc=5, credit_receipt=38, legit_repeat=8, midnight_fx=4, overpayment_refund=21, posting_lag=1, recurring=1, split_payment=2, twin_legit_repeat=1, unrelated=14 | 13.5 | 2 / 10 (0.2) | 0 / 584 |
| train | silent | 0 | - | - | 0 / 10 (0.0) | 0 / 0 |
