# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | -0.2045 | 0.4067 | 0.3 | 18.4 |
| 20 steps | recon | -0.9354 | 0.038 | 0.0 | 18.4 |
| 50 steps | auditor | 0.942 | 1.0 | 1.0 | 29.0 |
| 50 steps | recon | -0.7121 | 0.1667 | 0.0 | 29.0 |
| 100 steps | auditor | 0.942 | 1.0 | 1.0 | 29.0 |
| 100 steps | recon | -0.7121 | 0.1667 | 0.0 | 29.0 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | -0.2045 | -0.2045 | 0.3 | 0.175 | 1.0 | 0.1333 | 0.4067 | 0.4067 | 18.4 | 0.0091 | 0.3 | 0.968 | -0.4976 | 0 | 0.0 |
| dev | recon | 10 | -0.9354 | -0.914 | 0.022 | 0.15 | 0.0306 | 0.1 | 0.038 | 0.0487 | 18.4 | 0.0059 | 0.0 | -1.0 | -0.9192 | 11 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.942 | 0.942 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 29.0 | 0.0134 | 1.0 | 0.959 | 0.9378 | 0 | 0.0 |
| dev | recon | 10 | -0.7121 | -0.7121 | 0.1082 | 0.515 | 0.1124 | 0.6667 | 0.1667 | 0.1667 | 29.0 | 0.009 | 0.0 | -1.0 | -0.6401 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.942 | 0.942 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 29.0 | 0.0135 | 1.0 | 0.959 | 0.9378 | 0 | 0.0 |
| dev | recon | 10 | -0.7121 | -0.7121 | 0.1082 | 0.515 | 0.1124 | 0.6667 | 0.1667 | 0.1667 | 29.0 | 0.0091 | 0.0 | -1.0 | -0.6401 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
