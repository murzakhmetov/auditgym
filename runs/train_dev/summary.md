| split | policy | n | return | P | R | F1 | steps | agent s | closed | return clean | return errors | FP on clean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9466 | 0.8 | 0.8 | 1.0 | 26.7 | 0.0283 | 1.0 | 0.962 | 0.9427 | 0 |
| dev | flag_all | 10 | -1.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0093 | 0.0 | -1.0 | -1.0 | 60 |
| dev | oracle | 10 | 1.0 | 0.8 | 0.8 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 |
| dev | random | 10 | -1.0 | 0.0 | 0.0 | 0.0 | 15.0 | 0.0047 | 0.0 | -1.0 | -1.0 | 4 |
| dev | recon | 10 | -0.5449 | 0.1835 | 0.4733 | 0.2481 | 26.7 | 0.0157 | 0.0 | -1.0 | -0.4311 | 16 |
| train | auditor | 10 | 0.9698 | 0.7 | 0.7 | 1.0 | 15.1 | 0.011 | 1.0 | 0.9713 | 0.9691 | 0 |
| train | flag_all | 10 | -1.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0062 | 0.0 | -1.0 | -1.0 | 90 |
| train | oracle | 10 | 1.0 | 0.7 | 0.7 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 |
| train | random | 10 | -1.0 | 0.0 | 0.0 | 0.0 | 15.0 | 0.0032 | 0.0 | -1.0 | -1.0 | 6 |
| train | recon | 10 | -0.6375 | 0.1176 | 0.5 | 0.1883 | 15.1 | 0.0047 | 0.0 | -1.0 | -0.4822 | 11 |

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
