# auditgym check report

Result: **PASS** in 28 s, version 0.1.0.

## Checks

### A_unit_tests (1/1)

- PASS: unittest: 83 tests

### B_committed_episodes (40/40)

- PASS: train/t01_clean_small regenerates byte-identically
- PASS: train/t01_clean_small verifies (0 issues)
- PASS: train/t02_clean_distractors regenerates byte-identically
- PASS: train/t02_clean_distractors verifies (0 issues)
- PASS: train/t03_duplicate regenerates byte-identically
- PASS: train/t03_duplicate verifies (1 issues)
- PASS: train/t04_unallocated regenerates byte-identically
- PASS: train/t04_unallocated verifies (1 issues)
- PASS: train/t05_fx_rate regenerates byte-identically
- PASS: train/t05_fx_rate verifies (1 issues)
- PASS: train/t06_period regenerates byte-identically
- PASS: train/t06_period verifies (1 issues)
- PASS: train/t07_boundary_fx_payment regenerates byte-identically
- PASS: train/t07_boundary_fx_payment verifies (2 issues)
- PASS: train/t08_fx_partial_allocation regenerates byte-identically
- PASS: train/t08_fx_partial_allocation verifies (2 issues)
- PASS: train/t09_boundary_utc_clock regenerates byte-identically
- PASS: train/t09_boundary_utc_clock verifies (2 issues)
- PASS: train/t10_duplicate_twin_legit regenerates byte-identically
- PASS: train/t10_duplicate_twin_legit verifies (0 issues)
- PASS: dev/d01_clean_repeats_jpy regenerates byte-identically
- PASS: dev/d01_clean_repeats_jpy verifies (0 issues)
- PASS: dev/d02_clean_kwd_medium regenerates byte-identically
- PASS: dev/d02_clean_kwd_medium verifies (0 issues)
- PASS: dev/d03_duplicates_gbp regenerates byte-identically
- PASS: dev/d03_duplicates_gbp verifies (2 issues)
- PASS: dev/d04_unallocated_missing_eur regenerates byte-identically
- PASS: dev/d04_unallocated_missing_eur verifies (2 issues)
- PASS: dev/d05_fx_utc_stale_mixed_ts regenerates byte-identically
- PASS: dev/d05_fx_utc_stale_mixed_ts verifies (2 issues)
- PASS: dev/d06_period_dst_march regenerates byte-identically
- PASS: dev/d06_period_dst_march verifies (2 issues)
- PASS: dev/d07_boundary_negative_offset regenerates byte-identically
- PASS: dev/d07_boundary_negative_offset verifies (3 issues)
- PASS: dev/d08_both_interacting_kzt regenerates byte-identically
- PASS: dev/d08_both_interacting_kzt verifies (5 issues)
- PASS: dev/d09_large_mixed regenerates byte-identically
- PASS: dev/d09_large_mixed verifies (4 issues)
- PASS: dev/d10_large_dense_quarter_hour regenerates byte-identically
- PASS: dev/d10_large_dense_quarter_hour verifies (10 issues)

### C_data (21/21)

- PASS: h01_clean verifies (0 issues, 1 attempt(s))
- PASS: h02_clean verifies (0 issues, 1 attempt(s))
- PASS: h03_clean verifies (0 issues, 1 attempt(s))
- PASS: h04_clean verifies (0 issues, 1 attempt(s))
- PASS: h05_clean verifies (0 issues, 1 attempt(s))
- PASS: h06_interacting verifies (2 issues, 1 attempt(s))
- PASS: h07_interacting verifies (2 issues, 1 attempt(s))
- PASS: h08_interacting verifies (4 issues, 1 attempt(s))
- PASS: h09_interacting verifies (4 issues, 1 attempt(s))
- PASS: h10_interacting verifies (4 issues, 1 attempt(s))
- PASS: h11_mixed verifies (4 issues, 1 attempt(s))
- PASS: h12_mixed verifies (4 issues, 1 attempt(s))
- PASS: h13_mixed verifies (6 issues, 1 attempt(s))
- PASS: h14_mixed verifies (3 issues, 1 attempt(s))
- PASS: h15_mixed verifies (4 issues, 1 attempt(s))
- PASS: h16_mixed verifies (5 issues, 1 attempt(s))
- PASS: h17_mixed verifies (2 issues, 1 attempt(s))
- PASS: h18_mixed verifies (3 issues, 1 attempt(s))
- PASS: h19_mixed verifies (4 issues, 1 attempt(s))
- PASS: h20_mixed verifies (5 issues, 1 attempt(s))
- PASS: resampled attempts stay rare (0 over 20 episodes)

### C_reward (29/29)

- PASS: oracle reaches reward 1.0 on all 20 episodes
- PASS: flag-everything attack scores poorly (mean return <= -0.9)
- PASS: scripted auditor closes every episode (no FP, no FN)
- PASS: ordering: oracle > auditor > recon > flag_all
- PASS: random explorer stays far below the auditor
- PASS: every run finishes inside 100 steps and 60 s
- PASS: no agent process failed
- PASS: ep_a82d2576fa61f5f8: silence beats a false accusation on a clean ledger
- PASS: ep_a82d2576fa61f5f8: saving steps separates equal answers only slightly
- PASS: ep_a00ab5ca4acb3193: silence beats a false accusation on a clean ledger
- PASS: ep_a00ab5ca4acb3193: saving steps separates equal answers only slightly
- PASS: ep_30bc013036ba23ec: silence beats a false accusation on a clean ledger
- PASS: ep_30bc013036ba23ec: saving steps separates equal answers only slightly
- PASS: ep_0b0be35971deb0e4: correct answer with evidence beats silence
- PASS: ep_0b0be35971deb0e4: repeating findings gains nothing
- PASS: ep_0b0be35971deb0e4: guessed ids is not a true positive
- PASS: ep_0b0be35971deb0e4: unsupported evidence is not a true positive
- PASS: ep_0b0be35971deb0e4: wrong currency is not a true positive
- PASS: ep_0b0be35971deb0e4: amount off by 3 tolerances is not a true positive
- PASS: ep_0b0be35971deb0e4: citing documents by alias keeps full credit
- PASS: ep_0b0be35971deb0e4: saving steps separates equal answers only slightly
- PASS: ep_0751dd245072d0ab: correct answer with evidence beats silence
- PASS: ep_0751dd245072d0ab: repeating findings gains nothing
- PASS: ep_0751dd245072d0ab: guessed ids is not a true positive
- PASS: ep_0751dd245072d0ab: unsupported evidence is not a true positive
- PASS: ep_0751dd245072d0ab: wrong currency is not a true positive
- PASS: ep_0751dd245072d0ab: amount off by 3 tolerances is not a true positive
- PASS: ep_0751dd245072d0ab: citing documents by alias keeps full credit
- PASS: ep_0751dd245072d0ab: saving steps separates equal answers only slightly

### D_paired (27/27)

- PASS: h01_clean: same seed and config regenerate identical records and answer key
- PASS: h02_clean: same seed and config regenerate identical records and answer key
- PASS: h03_clean: same seed and config regenerate identical records and answer key
- PASS: h04_clean: same seed and config regenerate identical records and answer key
- PASS: h05_clean: same seed and config regenerate identical records and answer key
- PASS: h02_clean: same actions reproduce transitions and reward (random explorer)
- PASS: h02_clean: isolated child process and in-process runs are identical
- PASS: h01_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h01_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved

### E_leaks (3/3)

- PASS: 1732 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | P | R | F1 | steps | agent s | closed | return clean | return errors | FP on clean |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.9394 | 0.75 | 0.75 | 1.0 | 30.3 | 0.0126 | 1.0 | 0.9548 | 0.9343 | 0 |
| hidden_like | flag_all | 20 | -1.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.003 | 0.0 | -1.0 | -1.0 | 150 |
| hidden_like | oracle | 20 | 1.0 | 0.75 | 0.75 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 |
| hidden_like | random | 20 | -1.0 | 0.0 | 0.0 | 0.0 | 15.0 | 0.0016 | 0.0 | -1.0 | -1.0 | 10 |
| hidden_like | recon | 20 | -0.2191 | 0.3028 | 0.75 | 0.4151 | 30.3 | 0.0062 | 0.0 | -1.0 | 0.0411 | 24 |

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | amount=2, evidence=1, search=53 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |

