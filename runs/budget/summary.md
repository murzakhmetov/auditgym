# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | 0.4389 | 0.7362 | 0.4 | 18.6 |
| 20 steps | recon | -0.6723 | 0.1733 | 0.0 | 18.6 |
| 50 steps | auditor | 0.9492 | 1.0 | 1.0 | 25.4 |
| 50 steps | recon | -0.5341 | 0.2501 | 0.0 | 25.4 |
| 100 steps | auditor | 0.9492 | 1.0 | 1.0 | 25.4 |
| 100 steps | recon | -0.5341 | 0.2501 | 0.0 | 25.4 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.4389 | 0.4389 | 0.6667 | 0.4933 | 0.9474 | 0.6 | 0.7362 | 0.7362 | 18.6 | 0.0154 | 0.4 | 0.966 | 0.3072 | 0 | 0.0 |
| dev | recon | 10 | -0.6723 | -0.6523 | 0.1441 | 0.3 | 0.1121 | 0.4333 | 0.1733 | 0.1833 | 18.6 | 0.0083 | 0.0 | -1.0 | -0.5904 | 27 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9492 | 0.9492 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 25.4 | 0.0193 | 1.0 | 0.963 | 0.9457 | 0 | 0.0 |
| dev | recon | 10 | -0.5341 | -0.5341 | 0.1675 | 0.5567 | 0.1548 | 0.8 | 0.2501 | 0.2501 | 25.4 | 0.0109 | 0.0 | -1.0 | -0.4176 | 29 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9492 | 0.9492 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 25.4 | 0.0171 | 1.0 | 0.963 | 0.9457 | 0 | 0.0 |
| dev | recon | 10 | -0.5341 | -0.5341 | 0.1675 | 0.5567 | 0.1548 | 0.8 | 0.2501 | 0.2501 | 25.4 | 0.0103 | 0.0 | -1.0 | -0.4176 | 29 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
