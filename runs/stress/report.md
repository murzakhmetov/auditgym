# auditgym stress run

Random stream `auditgym-stress-v1`; counts are reproducible, timings and memory are not. Generated = verified + verify failed. Time is one untraced generation; memory is the tracemalloc peak of a second, traced generation of the same configuration.

| set | configs | generated | verified | verify failed | infeasible | gen failed | first attempt | later attempts | max gen s | peak MB |
|---|---|---|---|---|---|---|---|---|---|---|
| random | 300 | 282 | 282 | 0 | 18 | 0 | 260 | 22 | 0.38 | 6.1 |
| extreme | 17 | 17 | 17 | 0 | 0 | 0 | 14 | 3 | 0.30 | 5.5 |

## Extreme configurations (scripted auditor, in-process)

| name | status | attempts | gen s | auditor steps | closed |
|---|---|---|---|---|---|
| tz_America/New_York | verified | 1 | 0.08 | 11 | True |
| tz_America/Sao_Paulo | verified | 2 | 0.08 | 11 | True |
| tz_Asia/Almaty | verified | 1 | 0.08 | 11 | True |
| tz_Asia/Kathmandu | verified | 1 | 0.09 | 13 | True |
| tz_Asia/Kolkata | verified | 1 | 0.06 | 12 | True |
| tz_Asia/Kuwait | verified | 1 | 0.05 | 12 | True |
| tz_Asia/Tokyo | verified | 1 | 0.08 | 12 | True |
| tz_Australia/Sydney | verified | 1 | 0.08 | 11 | True |
| tz_Europe/Berlin | verified | 1 | 0.08 | 14 | True |
| tz_Europe/London | verified | 1 | 0.09 | 13 | True |
| tz_UTC | verified | 2 | 0.06 | 12 | True |
| exp_jpy_kwd_bhd | verified | 1 | 0.08 | 14 | True |
| exp_kwd_bhd_usd | verified | 1 | 0.08 | 13 | True |
| exp_usd_jpy_kwd | verified | 1 | 0.08 | 13 | True |
| year_boundary | verified | 2 | 0.08 | 11 | True |
| sydney_dst | verified | 1 | 0.09 | 12 | True |
| large_twelve | verified | 1 | 0.30 | 47 | True |

## Infeasible requests (ConfigError naming what is missing)

- 17 x boundary_fx_payment needs the last day of the period and the first day after it to be weekdays
- 1 x timezone UTC never has a UTC offset, but the requested errors need one

Total wall time 346 s.
