| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9492 | 0.9492 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 25.4 | 0.0128 | 1.0 | 0.963 | 0.9457 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0021 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -0.6098 | -0.6098 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 0.2 | 30.7 | 0.0039 | 0.2 | 0.951 | -1.0 | 0 | 0.0 |
| dev | recon | 10 | -0.5341 | -0.5341 | 0.1675 | 0.5567 | 0.1548 | 0.8 | 0.2501 | 0.2501 | 25.4 | 0.0077 | 0.0 | -1.0 | -0.4176 | 29 | 0.0 |
| dev | silent | 10 | -0.6 | -0.6 | 0.0 | 0.0 | n/a | 0.0 | 0.2 | 0.2 | 0.0 | 0.0002 | 0.2 | 1.0 | -1.0 | 0 | n/a |
| train | auditor | 10 | 0.9684 | 0.9684 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 15.8 | 0.0077 | 1.0 | 0.9733 | 0.9663 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0021 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -0.8004 | -0.8004 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 | 22.5 | 0.0033 | 0.1 | -0.3347 | -1.0 | 5 | 0.0 |
| train | recon | 10 | -0.9067 | -0.9067 | 0.0291 | 0.25 | 0.0205 | 0.3 | 0.0516 | 0.0516 | 15.8 | 0.0047 | 0.0 | -1.0 | -0.8667 | 39 | 0.0 |
| train | silent | 10 | -0.4 | -0.4 | 0.0 | 0.0 | n/a | 0.0 | 0.3 | 0.3 | 0.0 | 0.0002 | 0.3 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| dev | recon | duplicate_invoice=0.3333, unallocated_payment=1.0, wrong_fx_rate=0.7778, wrong_period=1.0 | not_flagged=6 |
| dev | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| train | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | recon | duplicate_invoice=0.0, unallocated_payment=1.0, wrong_fx_rate=0.3333, wrong_period=0.0 | not_flagged=7 |
| train | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| dev | auditor | 0.9492 | 0.9492 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -0.6098 | -0.6098 | 0.0 | 0.2 | 0.2 |
| dev | recon | -0.5341 | -0.5341 | 0.0 | 0.2501 | 0.2501 |
| dev | silent | -0.6 | -0.6 | 0.0 | 0.2 | 0.2 |
| train | auditor | 0.9684 | 0.9684 | 0.0 | 1.0 | 1.0 |
| train | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| train | random | -0.8004 | -0.8004 | 0.0 | 0.1 | 0.1 |
| train | recon | -0.9067 | -0.9067 | 0.0 | 0.0516 | 0.0516 |
| train | silent | -0.4 | -0.4 | 0.0 | 0.3 | 0.3 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| dev | auditor | 0 | - | 19.3333 | 0 / 30 (0.0) | 0 / 131 |
| dev | flag_all | 300 | boundary_doc=19, credit_receipt=28, legit_repeat=5, midnight_fx=1, multi_invoice_payment=10, near_issue=7, overpayment_refund=20, posting_lag=12, recurring=54, split_payment=29, underpayment=8, unrelated=102, weekend_fx=5 | - | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 131 / 131 |
| dev | random | 11 | legit_repeat=1, midnight_fx=1, posting_lag=1, recurring=1, split_payment=1, unrelated=6 | - | 0 / 30 (0.0) | 0 / 47 |
| dev | recon | 131 | credit_receipt=66, legit_repeat=13, midnight_fx=6, overpayment_refund=24, posting_lag=3, recurring=1, split_payment=2, unrelated=16 | 19.3333 | 6 / 30 (0.2) | 0 / 916 |
| dev | silent | 0 | - | - | 0 / 30 (0.0) | 0 / 0 |
| train | auditor | 0 | - | 14.7 | 0 / 10 (0.0) | 0 / 41 |
| train | flag_all | 300 | credit_receipt=38, legit_repeat=4, midnight_fx=2, overpayment_refund=25, recurring=51, split_payment=38, unrelated=140, weekend_fx=2 | - | 0 / 10 (0.0) | 0 / 190 |
| train | oracle | 0 | - | - | - | 41 / 41 |
| train | random | 13 | credit_receipt=2, midnight_fx=1, null_ref_receipt=2, split_payment=1, unrelated=7 | - | 0 / 10 (0.0) | 0 / 45 |
| train | recon | 143 | boundary_doc=28, credit_receipt=57, legit_repeat=5, midnight_fx=6, near_issue=1, overpayment_refund=20, posting_lag=1, recurring=4, split_payment=3, unrelated=18 | 14.7 | 7 / 10 (0.7) | 0 / 742 |
| train | silent | 0 | - | - | 0 / 10 (0.0) | 0 / 0 |
