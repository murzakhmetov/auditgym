# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | -0.0982 | 0.4638 | 0.2 | 18.6 |
| 20 steps | recon | -0.9205 | 0.0474 | 0.0 | 18.6 |
| 50 steps | auditor | 0.946 | 1.0 | 1.0 | 27.0 |
| 50 steps | recon | -0.7744 | 0.1332 | 0.0 | 27.0 |
| 100 steps | auditor | 0.946 | 1.0 | 1.0 | 27.0 |
| 100 steps | recon | -0.7744 | 0.1332 | 0.0 | 27.0 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | -0.0982 | -0.0982 | 0.4 | 0.215 | 0.6 | 0.2 | 0.4638 | 0.4638 | 18.6 | 0.0093 | 0.2 | 0.966 | -0.3642 | 0 | 0.0 |
| dev | recon | 10 | -0.9205 | -0.9066 | 0.0295 | 0.145 | 0.0317 | 0.1333 | 0.0474 | 0.0562 | 18.6 | 0.0056 | 0.0 | -1.0 | -0.9006 | 15 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.946 | 0.946 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 27.0 | 0.0137 | 1.0 | 0.961 | 0.9423 | 0 | 0.0 |
| dev | recon | 10 | -0.7744 | -0.7744 | 0.0813 | 0.4683 | 0.0923 | 0.6 | 0.1332 | 0.1332 | 27.0 | 0.0085 | 0.0 | -1.0 | -0.718 | 16 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.946 | 0.946 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 27.0 | 0.0138 | 1.0 | 0.961 | 0.9423 | 0 | 0.0 |
| dev | recon | 10 | -0.7744 | -0.7744 | 0.0813 | 0.4683 | 0.0923 | 0.6 | 0.1332 | 0.1332 | 27.0 | 0.0089 | 0.0 | -1.0 | -0.718 | 16 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
