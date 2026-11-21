| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.946 | 0.946 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 27.0 | 0.0125 | 1.0 | 0.961 | 0.9423 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0031 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -0.8008 | -0.8008 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 | 29.0 | 0.0048 | 0.1 | -0.004 | -1.0 | 3 | 0.0 |
| dev | recon | 10 | -0.7744 | -0.7744 | 0.0813 | 0.4683 | 0.0923 | 0.6 | 0.1332 | 0.1332 | 27.0 | 0.0093 | 0.0 | -1.0 | -0.718 | 16 | 0.0 |
| dev | silent | 10 | -0.6 | -0.6 | 0.0 | 0.0 | n/a | 0.0 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 1.0 | -1.0 | 0 | n/a |
| train | auditor | 10 | 0.9702 | 0.9702 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 14.9 | 0.0046 | 1.0 | 0.9753 | 0.968 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0031 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -0.6072 | -0.6072 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 0.2 | 24.0 | 0.0047 | 0.2 | 0.3093 | -1.0 | 2 | 0.0 |
| train | recon | 10 | -0.8474 | -0.8474 | 0.0471 | 0.4 | 0.0424 | 0.5 | 0.0827 | 0.0827 | 14.9 | 0.0031 | 0.0 | -1.0 | -0.782 | 31 | 0.0 |
| train | silent | 10 | -0.4 | -0.4 | 0.0 | 0.0 | n/a | 0.0 | 0.3 | 0.3 | 0.0 | 0.0016 | 0.3 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | recon | duplicate_invoice=0.3333, unallocated_payment=1.0, wrong_fx_rate=0.4444, wrong_period=0.625 | not_flagged=12 |
| dev | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| train | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | not_flagged=1, search=9 |
| train | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | recon | duplicate_invoice=0.0, unallocated_payment=1.0, wrong_fx_rate=0.6667, wrong_period=0.25 | not_flagged=5 |
| train | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| dev | auditor | 0.946 | 0.946 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -0.8008 | -0.8008 | 0.0 | 0.1 | 0.1 |
| dev | recon | -0.7744 | -0.7744 | 0.0 | 0.1332 | 0.1332 |
| dev | silent | -0.6 | -0.6 | 0.0 | 0.2 | 0.2 |
| train | auditor | 0.9702 | 0.9702 | 0.0 | 1.0 | 1.0 |
| train | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| train | random | -0.6072 | -0.6072 | 0.0 | 0.2 | 0.2 |
| train | recon | -0.8474 | -0.8474 | 0.0 | 0.0827 | 0.0827 |
| train | silent | -0.4 | -0.4 | 0.0 | 0.3 | 0.3 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| dev | auditor | 0 | - | 23.5333 | 0 / 30 (0.0) | 0 / 135 |
| dev | flag_all | 300 | boundary_doc=28, credit_receipt=31, legit_repeat=5, midnight_fx=9, near_issue=5, overpayment_refund=10, posting_lag=19, recurring=46, split_payment=26, underpayment=4, unrelated=117 | - | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 135 / 135 |
| dev | random | 13 | credit_receipt=1, near_issue=1, posting_lag=1, recurring=1, split_payment=3, unrelated=5, weekend_fx=1 | - | 0 / 30 (0.0) | 0 / 39 |
| dev | recon | 177 | boundary_doc=27, credit_receipt=60, legit_repeat=10, midnight_fx=13, multi_invoice_payment=1, null_ref_receipt=1, overpayment_refund=19, posting_lag=4, recurring=6, split_payment=7, underpayment=1, unrelated=27, weekend_fx=1 | 23.5333 | 12 / 30 (0.4) | 0 / 951 |
| dev | silent | 0 | - | - | 0 / 30 (0.0) | 0 / 0 |
| train | auditor | 0 | - | 11.0 | 0 / 10 (0.0) | 0 / 39 |
| train | flag_all | 300 | boundary_doc=20, credit_receipt=26, legit_repeat=14, midnight_fx=22, multi_invoice_payment=20, near_issue=5, overpayment_refund=8, posting_lag=9, recurring=26, split_payment=14, unrelated=136 | 3.0 | 1 / 10 (0.1) | 0 / 190 |
| train | oracle | 0 | - | - | - | 39 / 39 |
| train | random | 14 | credit_receipt=1, legit_repeat=2, posting_lag=1, recurring=1, split_payment=1, unrelated=8 | - | 0 / 10 (0.0) | 0 / 46 |
| train | recon | 113 | boundary_doc=11, credit_receipt=50, legit_repeat=14, midnight_fx=9, multi_invoice_payment=1, overpayment_refund=21, unrelated=7 | 11.0 | 5 / 10 (0.5) | 0 / 717 |
| train | silent | 0 | - | - | 0 / 10 (0.0) | 0 / 0 |
