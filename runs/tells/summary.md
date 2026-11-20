# Shortcut-tell measurement

Master string `auditgym-tells-v1`, 1000 generated episodes (750 with errors), 141479 public documents, 3799 affected documents (the answer key).
Reproduce: `python -m auditgym.tells --n 1000 --master auditgym-tells-v1 --out runs/tells`.

A rule fires on the documents it selects. True hits are fired documents that are in the answer key; precision = hits / fires on; recall = hits / affected documents; support = episodes in which the rule fires at least once.

| rule | fires on | true hits | precision | recall | support |
|---|---:|---:|---:|---:|---:|
| paid twin invoice | 1297 | 300 | 0.2313 | 0.0790 | 800 |
| same-instant pair, terms != 30 or one copy paid | 4306 | 942 | 0.2188 | 0.2480 | 969 |
| invoice with a twin | 5070 | 1106 | 0.2181 | 0.2911 | 1000 |
| payment with a 2900 row and invoice refs | 3322 | 718 | 0.2161 | 0.1890 | 1000 |
| unpaid twin invoice | 3773 | 806 | 0.2136 | 0.2122 | 1000 |
| same-instant pair with terms != 30 | 3472 | 740 | 0.2131 | 0.1948 | 892 |
| receipt in the error window | 996 | 150 | 0.1506 | 0.0395 | 601 |
| payment with a 2900 row | 6002 | 718 | 0.1196 | 0.1890 | 1000 |
| purchase invoice in the error window | 813 | 93 | 0.1144 | 0.0245 | 543 |
| residual: off-hours payment inside the error window | 1585 | 147 | 0.0927 | 0.0387 | 752 |
| sales invoice in the error window | 829 | 73 | 0.0881 | 0.0192 | 541 |
| near-midnight (UTC date differs) invoice | 6711 | 418 | 0.0623 | 0.1100 | 890 |
| boundary day, off-hours invoice | 2912 | 162 | 0.0556 | 0.0426 | 960 |
| off-hours invoice | 8384 | 452 | 0.0539 | 0.1190 | 1000 |
| boundary day, off-hours payment | 3250 | 149 | 0.0458 | 0.0392 | 971 |
| top-3 foreign purchase | 2989 | 121 | 0.0405 | 0.0319 | 999 |
| within 12 h of period boundary | 9719 | 389 | 0.0400 | 0.1024 | 1000 |
| off-hours document | 19231 | 701 | 0.0365 | 0.1845 | 1000 |
| top-3 foreign sale | 3000 | 106 | 0.0353 | 0.0279 | 1000 |
| terms not 30 days | 55410 | 1949 | 0.0352 | 0.5130 | 1000 |
| terms 14 or 45 days | 54977 | 1930 | 0.0351 | 0.5080 | 1000 |
| near-midnight (UTC date differs) payment | 5932 | 199 | 0.0335 | 0.0524 | 890 |
| largest foreign sale | 1000 | 33 | 0.0330 | 0.0087 | 1000 |
| largest foreign purchase | 999 | 27 | 0.0270 | 0.0071 | 999 |
| weekday date | 127143 | 3417 | 0.0269 | 0.8994 | 1000 |
| weekend date | 14336 | 382 | 0.0266 | 0.1006 | 1000 |
| document on an FX holiday | 4601 | 117 | 0.0254 | 0.0308 | 650 |
| dominant foreign purchase (>= 1.5x runner-up) | 199 | 5 | 0.0251 | 0.0013 | 199 |
| off-hours payment | 10847 | 249 | 0.0230 | 0.0655 | 1000 |
| residual: off-hours payment | 10847 | 249 | 0.0230 | 0.0655 | 1000 |
| round amount | 2346 | 46 | 0.0196 | 0.0121 | 371 |
| largest invoice | 1000 | 18 | 0.0180 | 0.0047 | 1000 |
| residual: off-hours payment outside the error window | 9262 | 102 | 0.0110 | 0.0268 | 1000 |
| disbursement in the error window | 672 | 0 | 0.0000 | 0.0000 | 480 |
| qty/price outside catalogue | 0 | 0 | 0.0000 | 0.0000 | 0 |
| sales qty above catalogue max | 0 | 0 | 0.0000 | 0.0000 | 0 |

## Episode-level rules

Base rate: 750 of 1000 episodes have errors (0.7500) and 250 are clean (0.2500). A rule is a tell only if its precision is well above the base rate of its label.

| rule | label | episodes flagged | correct | precision | base rate of the label |
|---|---|---:|---:|---:|---:|
| any quantity/price outside catalogue -> error | error | 0 | 0 | 0.0000 | 0.7500 |
| any off-hours payment on a boundary day -> error | error | 971 | 731 | 0.7528 | 0.7500 |
| any same-instant pair with terms != 30 -> error | error | 892 | 687 | 0.7702 | 0.7500 |
| small ledger (< 500 rows) with >= 2 refunds -> clean | clean | 0 | 0 | 0.0000 | 0.2500 |
| small ledger (< 500 rows) with >= 3 null-ref receipts -> clean | clean | 0 | 0 | 0.0000 | 0.2500 |

## FX target and the largest foreign purchase

Among the 180 episodes whose answer key has a wrong_fx_rate target that is a foreign purchase invoice, the largest foreign purchase is such a target in 17 (rate 0.0944). Chance level, the mean share of foreign purchases that are targets: 0.1025.

## Measured only in the regression test

The episode rules on the count of documents in the error window (more or fewer than the typical count, by size and kind) and the window-by-kind rules scored against utc_wall_clock targets only are measured in tests/test_tells.py on 100 generated episodes. The window rows above are scored against all affected documents.
