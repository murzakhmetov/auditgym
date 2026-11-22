| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.0144 | 1.0 | 0.959 | 0.9385 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0026 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 29.3 | 0.0043 | 0.0 | -1.0 | -1.0 | 5 | 0.0 |
| dev | recon | 10 | -0.7328 | -0.7328 | 0.1027 | 0.505 | 0.1044 | 0.6333 | 0.156 | 0.156 | 28.7 | 0.0096 | 0.0 | -1.0 | -0.666 | 14 | 0.0 |
| dev | silent | 10 | -0.6 | -0.6 | 0.0 | 0.0 | n/a | 0.0 | 0.2 | 0.2 | 0.0 | 0.0002 | 0.2 | 1.0 | -1.0 | 0 | n/a |
| train | auditor | 10 | 0.969 | 0.969 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 15.5 | 0.008 | 1.0 | 0.9747 | 0.9666 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.002 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 29.7 | 0.0052 | 0.0 | -1.0 | -1.0 | 7 | 0.0 |
| train | recon | 10 | -0.7247 | -0.7247 | 0.0848 | 0.6 | 0.0777 | 0.8 | 0.1479 | 0.1479 | 15.5 | 0.0053 | 0.0 | -1.0 | -0.6067 | 36 | 0.0 |
| train | silent | 10 | -0.4 | -0.4 | 0.0 | 0.0 | n/a | 0.0 | 0.3 | 0.3 | 0.0 | 0.0002 | 0.3 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | recon | duplicate_invoice=0.3333, unallocated_payment=1.0, wrong_fx_rate=0.5556, wrong_period=0.625 | not_flagged=11 |
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
| dev | auditor | 0.9426 | 0.9426 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | recon | -0.7328 | -0.7328 | 0.0 | 0.156 | 0.156 |
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
| dev | auditor | 0 | - | 24.7333 | 0 / 30 (0.0) | 0 / 135 |
| dev | flag_all | 300 | credit_receipt=22, legit_repeat=9, midnight_fx=1, multi_invoice_payment=1, near_issue=9, overpayment_refund=20, posting_lag=4, recurring=72, split_payment=11, unrelated=151 | - | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 135 / 135 |
| dev | random | 14 | credit_receipt=1, multi_invoice_payment=1, overpayment_refund=1, recurring=2, unrelated=9 | - | 0 / 30 (0.0) | 0 / 40 |
| dev | recon | 163 | boundary_doc=16, credit_receipt=56, legit_repeat=7, midnight_fx=14, near_issue=2, overpayment_refund=28, posting_lag=2, recurring=6, split_payment=4, unrelated=28 | 24.7333 | 11 / 30 (0.3667) | 0 / 972 |
| dev | silent | 0 | - | - | 0 / 30 (0.0) | 0 / 0 |
| train | auditor | 0 | - | 13.5 | 0 / 10 (0.0) | 0 / 39 |
| train | flag_all | 300 | boundary_doc=31, credit_receipt=20, legit_repeat=15, midnight_fx=10, multi_invoice_payment=10, near_issue=4, overpayment_refund=21, posting_lag=26, recurring=22, split_payment=30, underpayment=4, unrelated=100, weekend_fx=7 | 3.0 | 1 / 10 (0.1) | 0 / 190 |
| train | oracle | 0 | - | - | - | 39 / 39 |
| train | random | 18 | credit_receipt=1, legit_repeat=1, overpayment_refund=1, split_payment=4, underpayment=1, unrelated=10 | - | 0 / 10 (0.0) | 0 / 56 |
| train | recon | 95 | boundary_doc=5, credit_receipt=38, legit_repeat=8, midnight_fx=4, overpayment_refund=21, posting_lag=1, recurring=1, split_payment=2, twin_legit_repeat=1, unrelated=14 | 13.5 | 2 / 10 (0.2) | 0 / 584 |
| train | silent | 0 | - | - | 0 / 10 (0.0) | 0 / 0 |
