# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | -0.1719 | 0.4248 | 0.3 | 18.4 |
| 20 steps | recon | -0.8874 | 0.0658 | 0.0 | 18.4 |
| 50 steps | auditor | 0.942 | 1.0 | 1.0 | 29.0 |
| 50 steps | recon | -0.7393 | 0.1531 | 0.0 | 29.0 |
| 100 steps | auditor | 0.942 | 1.0 | 1.0 | 29.0 |
| 100 steps | recon | -0.7393 | 0.1531 | 0.0 | 29.0 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | -0.1719 | -0.1719 | 0.4 | 0.185 | 1.0 | 0.1667 | 0.4248 | 0.4248 | 18.4 | 0.0095 | 0.3 | 0.968 | -0.4569 | 0 | 0.0 |
| dev | recon | 10 | -0.8874 | -0.8493 | 0.047 | 0.185 | 0.0463 | 0.1667 | 0.0658 | 0.0848 | 18.4 | 0.0053 | 0.0 | -1.0 | -0.8593 | 11 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.942 | 0.942 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 29.0 | 0.0142 | 1.0 | 0.959 | 0.9378 | 0 | 0.0 |
| dev | recon | 10 | -0.7393 | -0.7393 | 0.0942 | 0.535 | 0.1111 | 0.7333 | 0.1531 | 0.1531 | 29.0 | 0.0093 | 0.0 | -1.0 | -0.6741 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.942 | 0.942 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 29.0 | 0.0167 | 1.0 | 0.959 | 0.9378 | 0 | 0.0 |
| dev | recon | 10 | -0.7393 | -0.7393 | 0.0942 | 0.535 | 0.1111 | 0.7333 | 0.1531 | 0.1531 | 29.0 | 0.0091 | 0.0 | -1.0 | -0.6741 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
