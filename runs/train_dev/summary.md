| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.0139 | 1.0 | 0.961 | 0.938 | 0 | 0.0 |
| dev | flag_all | 10 | -1.0 | -0.992 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0043 | 3.0 | 0.0016 | 0.0 | -1.0 | -1.0 | 60 | 0.0 |
| dev | oracle | 10 | 1.0 | 1.0 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| dev | random | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 18.9 | 0.0045 | 0.0 | -1.0 | -1.0 | 5 | 0.0 |
| dev | recon | 10 | -0.6886 | -0.6886 | 0.1184 | 0.4483 | 0.1417 | 0.5667 | 0.1778 | 0.1778 | 28.7 | 0.0078 | 0.0 | -1.0 | -0.6108 | 5 | 0.0 |
| dev | silent | 10 | -0.6 | -0.6 | 0.0 | 0.0 | n/a | 0.0 | 0.2 | 0.2 | 0.0 | 0.0 | 0.2 | 1.0 | -1.0 | 0 | n/a |
| train | auditor | 10 | 0.9714 | 0.9714 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 14.3 | 0.0063 | 1.0 | 0.9747 | 0.97 | 0 | 0.0 |
| train | flag_all | 10 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0032 | 0.0 | -1.0 | -1.0 | 90 | 0.0 |
| train | oracle | 10 | 1.0 | 1.0 | 0.7 | 0.7 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| train | random | 10 | -0.6132 | -0.6132 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 0.2 | 19.3 | 0.003 | 0.2 | 0.2893 | -1.0 | 1 | 0.0 |
| train | recon | 10 | -0.6902 | -0.6902 | 0.0997 | 0.5 | 0.08 | 0.6 | 0.1612 | 0.1612 | 14.3 | 0.0061 | 0.0 | -1.0 | -0.5574 | 26 | 0.0 |
| train | silent | 10 | -0.4 | -0.4 | 0.0 | 0.0 | n/a | 0.0 | 0.3 | 0.3 | 0.0 | 0.0 | 0.3 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| dev | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | evidence=1, search=29 |
| dev | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| dev | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | not_flagged=1, search=29 |
| dev | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=0.2222, wrong_period=0.25 | not_flagged=13 |
| dev | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=30 |
| train | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| train | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |
| train | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=0.6667, wrong_period=0.25 | not_flagged=4 |
| train | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=10 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| dev | auditor | 0.9426 | 0.9426 | 0.0 | 1.0 | 1.0 |
| dev | flag_all | -1.0 | -0.992 | 0.008 | 0.0 | 0.0043 |
| dev | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| dev | random | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| dev | recon | -0.6886 | -0.6886 | 0.0 | 0.1778 | 0.1778 |
| dev | silent | -0.6 | -0.6 | 0.0 | 0.2 | 0.2 |
| train | auditor | 0.9714 | 0.9714 | 0.0 | 1.0 | 1.0 |
| train | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| train | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| train | random | -0.6132 | -0.6132 | 0.0 | 0.2 | 0.2 |
| train | recon | -0.6902 | -0.6902 | 0.0 | 0.1612 | 0.1612 |
| train | silent | -0.4 | -0.4 | 0.0 | 0.3 | 0.3 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| dev | auditor | 0 | - | 23.0333 | 0 / 30 (0.0) | 0 / 133 |
| dev | flag_all | 300 | boundary_doc=25, legit_repeat=9, midnight_fx=16, multi_invoice_payment=5, near_issue=5, overpayment_refund=4, recurring=22, unrelated=211, weekend_fx=3 | 3.0 | 0 / 30 (0.0) | 0 / 190 |
| dev | oracle | 0 | - | - | - | 133 / 133 |
| dev | random | 16 | boundary_doc=2, midnight_fx=1, null_ref_receipt=1, split_payment=1, unrelated=11 | 10.0 | 1 / 30 (0.0333) | 0 / 53 |
| dev | recon | 103 | boundary_doc=25, legit_repeat=20, midnight_fx=13, overpayment_refund=13, recurring=7, unrelated=25 | 23.0333 | 13 / 30 (0.4333) | 0 / 542 |
| dev | silent | 0 | - | - | 0 / 30 (0.0) | 0 / 0 |
| train | auditor | 0 | - | 13.3 | 0 / 10 (0.0) | 0 / 39 |
| train | flag_all | 300 | boundary_doc=10, legit_repeat=13, multi_invoice_payment=15, overpayment_refund=5, recurring=38, split_payment=5, unrelated=211, weekend_fx=3 | - | 0 / 10 (0.0) | 0 / 190 |
| train | oracle | 0 | - | - | - | 39 / 39 |
| train | random | 13 | boundary_doc=1, midnight_fx=1, unrelated=11 | - | 0 / 10 (0.0) | 0 / 41 |
| train | recon | 69 | boundary_doc=19, legit_repeat=12, midnight_fx=13, multi_invoice_payment=1, null_ref_receipt=1, overpayment_refund=10, twin_legit_repeat=1, unrelated=12 | 13.3 | 4 / 10 (0.4) | 0 / 331 |
| train | silent | 0 | - | - | 0 / 10 (0.0) | 0 / 0 |
