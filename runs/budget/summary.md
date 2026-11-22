# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | -0.2807 | 0.3667 | 0.3 | 18.4 |
| 20 steps | recon | -0.9142 | 0.0505 | 0.0 | 18.4 |
| 50 steps | auditor | 0.9426 | 1.0 | 1.0 | 28.7 |
| 50 steps | recon | -0.7328 | 0.156 | 0.0 | 28.7 |
| 100 steps | auditor | 0.9426 | 1.0 | 1.0 | 28.7 |
| 100 steps | recon | -0.7328 | 0.156 | 0.0 | 28.7 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | -0.2807 | -0.2807 | 0.2 | 0.15 | 1.0 | 0.1 | 0.3667 | 0.3667 | 18.4 | 0.0087 | 0.3 | 0.968 | -0.5928 | 0 | 0.0 |
| dev | recon | 10 | -0.9142 | -0.8553 | 0.0386 | 0.16 | 0.0388 | 0.1333 | 0.0505 | 0.08 | 18.4 | 0.006 | 0.0 | -1.0 | -0.8927 | 11 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.014 | 1.0 | 0.959 | 0.9385 | 0 | 0.0 |
| dev | recon | 10 | -0.7328 | -0.7328 | 0.1027 | 0.505 | 0.1044 | 0.6333 | 0.156 | 0.156 | 28.7 | 0.0103 | 0.0 | -1.0 | -0.666 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.0128 | 1.0 | 0.959 | 0.9385 | 0 | 0.0 |
| dev | recon | 10 | -0.7328 | -0.7328 | 0.1027 | 0.505 | 0.1044 | 0.6333 | 0.156 | 0.156 | 28.7 | 0.0087 | 0.0 | -1.0 | -0.666 | 14 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
