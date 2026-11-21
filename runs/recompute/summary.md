# Independent key recompute

`tools/recompute_keys.py`: every answer-key amount recomputed from the public records alone (policy, FX table, invoices, payments, ledger), standard library only, no import of `auditgym` (see the docstring of the tool for the checks).

- episodes: 120
- issues: 307
- recomputed and equal to the key: 307
- differing: 0

| type / side of the target | issues | recomputed |
|---|---|---|
| duplicate_invoice / pair | 64 | 64 |
| unallocated_payment / receipt | 82 | 82 |
| wrong_fx_rate / disbursement | 16 | 16 |
| wrong_fx_rate / invoice | 28 | 28 |
| wrong_fx_rate / receipt | 35 | 35 |
| wrong_period / disbursement | 13 | 13 |
| wrong_period / invoice | 23 | 23 |
| wrong_period / receipt | 46 | 46 |
