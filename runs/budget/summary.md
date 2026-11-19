# Action budget (dev, scripted auditor and recon, isolated, eval mode)

| budget | policy | return | F1 | closed share | steps |
|---|---|---|---|---|---|
| 20 steps | auditor | -0.0826 | 0.4715 | 0.2 | 18.5 |
| 20 steps | recon | -0.8485 | 0.0815 | 0.0 | 18.5 |
| 50 steps | auditor | 0.9426 | 1.0 | 1.0 | 28.7 |
| 50 steps | recon | -0.6886 | 0.1778 | 0.0 | 28.7 |
| 100 steps | auditor | 0.9426 | 1.0 | 1.0 | 28.7 |
| 100 steps | recon | -0.6886 | 0.1778 | 0.0 | 28.7 |

Reproduce: `python -m auditgym budget --budgets 20,50,100` (or `make budget`).

## 20 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | -0.0826 | -0.0826 | 0.5 | 0.2017 | 1.0 | 0.2 | 0.4715 | 0.4715 | 18.5 | 0.0063 | 0.2 | 0.967 | -0.345 | 0 | 0.0 |
| dev | recon | 10 | -0.8485 | -0.8485 | 0.0679 | 0.11 | 0.0727 | 0.1333 | 0.0815 | 0.0815 | 18.5 | 0.0062 | 0.0 | -1.0 | -0.8106 | 4 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 50 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.0077 | 1.0 | 0.961 | 0.938 | 0 | 0.0 |
| dev | recon | 10 | -0.6886 | -0.6886 | 0.1184 | 0.4483 | 0.1417 | 0.5667 | 0.1778 | 0.1778 | 28.7 | 0.0063 | 0.0 | -1.0 | -0.6108 | 5 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## 100 steps

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | auditor | 10 | 0.9426 | 0.9426 | 0.8 | 0.8 | 1.0 | 1.0 | 1.0 | 1.0 | 28.7 | 0.0155 | 1.0 | 0.961 | 0.938 | 0 | 0.0 |
| dev | recon | 10 | -0.6886 | -0.6886 | 0.1184 | 0.4483 | 0.1417 | 0.5667 | 0.1778 | 0.1778 | 28.7 | 0.0062 | 0.0 | -1.0 | -0.6108 | 5 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).
