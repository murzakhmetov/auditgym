# auditgym check report

Result: **FAIL** in 54 s, version 0.1.0.

Episodes: public master string auditgym-check-v1.

## Checks (grouped by rubric criterion)

### 1. Contract and isolation (25)

Run time: E_leaks 0.4 s

#### E_leaks (3/3)

- PASS: 1996 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

### 2. Data and answer key (25)

Run time: B_committed_episodes 3.2 s, C_data 4.0 s

#### B_committed_episodes (40/40)

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

#### C_data (21/21)

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

### 3. Reward reliability (25)

Run time: C_reward 13.2 s

#### C_reward (248/248)

- PASS: oracle reaches reward 1.0 on all 20 episodes
- PASS: flag-everything attack scores poorly (mean return <= -0.9)
- PASS: scripted auditor closes every episode (no FP, no FN)
- PASS: ordering: oracle > auditor > recon > flag_all
- PASS: ordering on error episodes only: auditor > recon >= flag_all
- PASS: random explorer stays far below the auditor
- PASS: every run finishes inside 100 steps and 60 s
- PASS: no agent process failed
- PASS: ep_a82d2576fa61f5f8: silence beats a false accusation on a clean ledger
- PASS: ep_a82d2576fa61f5f8: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_a82d2576fa61f5f8: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_a82d2576fa61f5f8: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_a82d2576fa61f5f8: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_a82d2576fa61f5f8: saving steps separates equal answers only slightly
- PASS: ep_a00ab5ca4acb3193: silence beats a false accusation on a clean ledger
- PASS: ep_a00ab5ca4acb3193: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_a00ab5ca4acb3193: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_a00ab5ca4acb3193: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_a00ab5ca4acb3193: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_a00ab5ca4acb3193: saving steps separates equal answers only slightly
- PASS: ep_30bc013036ba23ec: silence beats a false accusation on a clean ledger
- PASS: ep_30bc013036ba23ec: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_30bc013036ba23ec: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_30bc013036ba23ec: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_30bc013036ba23ec: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_30bc013036ba23ec: saving steps separates equal answers only slightly
- PASS: ep_80fb3a5fb4e900a3: silence beats a false accusation on a clean ledger
- PASS: ep_80fb3a5fb4e900a3: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_80fb3a5fb4e900a3: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_80fb3a5fb4e900a3: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_80fb3a5fb4e900a3: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_80fb3a5fb4e900a3: saving steps separates equal answers only slightly
- PASS: ep_a6d58011c890d230: silence beats a false accusation on a clean ledger
- PASS: ep_a6d58011c890d230: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_a6d58011c890d230: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_a6d58011c890d230: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_a6d58011c890d230: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_a6d58011c890d230: saving steps separates equal answers only slightly
- PASS: ep_4cb4198a3243a5b3: correct answer with evidence beats silence
- PASS: ep_4cb4198a3243a5b3: repeating findings gains nothing
- PASS: ep_4cb4198a3243a5b3: guessed ids is not a true positive
- PASS: ep_4cb4198a3243a5b3: unsupported evidence is not a true positive
- PASS: ep_4cb4198a3243a5b3: wrong currency is not a true positive
- PASS: ep_4cb4198a3243a5b3: amount off by 3 tolerances is not a true positive
- PASS: ep_4cb4198a3243a5b3: wrong type is not a true positive
- PASS: ep_4cb4198a3243a5b3: citing documents by alias keeps full credit
- PASS: ep_4cb4198a3243a5b3: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_4cb4198a3243a5b3: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_4cb4198a3243a5b3: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_4cb4198a3243a5b3: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_4cb4198a3243a5b3: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_4cb4198a3243a5b3: saving steps separates equal answers only slightly
- PASS: ep_9f67c47403029e75: correct answer with evidence beats silence
- PASS: ep_9f67c47403029e75: repeating findings gains nothing
- PASS: ep_9f67c47403029e75: guessed ids is not a true positive
- PASS: ep_9f67c47403029e75: unsupported evidence is not a true positive
- PASS: ep_9f67c47403029e75: wrong currency is not a true positive
- PASS: ep_9f67c47403029e75: amount off by 3 tolerances is not a true positive
- PASS: ep_9f67c47403029e75: wrong type is not a true positive
- PASS: ep_9f67c47403029e75: citing documents by alias keeps full credit
- PASS: ep_9f67c47403029e75: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_9f67c47403029e75: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_9f67c47403029e75: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_9f67c47403029e75: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_9f67c47403029e75: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_9f67c47403029e75: saving steps separates equal answers only slightly
- PASS: ep_da108ee499ec5995: correct answer with evidence beats silence
- PASS: ep_da108ee499ec5995: repeating findings gains nothing
- PASS: ep_da108ee499ec5995: guessed ids is not a true positive
- PASS: ep_da108ee499ec5995: unsupported evidence is not a true positive
- PASS: ep_da108ee499ec5995: wrong currency is not a true positive
- PASS: ep_da108ee499ec5995: amount off by 3 tolerances is not a true positive
- PASS: ep_da108ee499ec5995: wrong type is not a true positive
- PASS: ep_da108ee499ec5995: citing documents by alias keeps full credit
- PASS: ep_da108ee499ec5995: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_da108ee499ec5995: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_da108ee499ec5995: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_da108ee499ec5995: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_da108ee499ec5995: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_da108ee499ec5995: saving steps separates equal answers only slightly
- PASS: ep_365723c029c0d7a4: correct answer with evidence beats silence
- PASS: ep_365723c029c0d7a4: repeating findings gains nothing
- PASS: ep_365723c029c0d7a4: guessed ids is not a true positive
- PASS: ep_365723c029c0d7a4: unsupported evidence is not a true positive
- PASS: ep_365723c029c0d7a4: wrong currency is not a true positive
- PASS: ep_365723c029c0d7a4: amount off by 3 tolerances is not a true positive
- PASS: ep_365723c029c0d7a4: wrong type is not a true positive
- PASS: ep_365723c029c0d7a4: citing documents by alias keeps full credit
- PASS: ep_365723c029c0d7a4: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_365723c029c0d7a4: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_365723c029c0d7a4: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_365723c029c0d7a4: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_365723c029c0d7a4: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_365723c029c0d7a4: saving steps separates equal answers only slightly
- PASS: ep_802da4715873f0c2: correct answer with evidence beats silence
- PASS: ep_802da4715873f0c2: repeating findings gains nothing
- PASS: ep_802da4715873f0c2: guessed ids is not a true positive
- PASS: ep_802da4715873f0c2: unsupported evidence is not a true positive
- PASS: ep_802da4715873f0c2: wrong currency is not a true positive
- PASS: ep_802da4715873f0c2: amount off by 3 tolerances is not a true positive
- PASS: ep_802da4715873f0c2: wrong type is not a true positive
- PASS: ep_802da4715873f0c2: citing documents by alias keeps full credit
- PASS: ep_802da4715873f0c2: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_802da4715873f0c2: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_802da4715873f0c2: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_802da4715873f0c2: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_802da4715873f0c2: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_802da4715873f0c2: saving steps separates equal answers only slightly
- PASS: ep_7ed3c2e72317ce46: correct answer with evidence beats silence
- PASS: ep_7ed3c2e72317ce46: repeating findings gains nothing
- PASS: ep_7ed3c2e72317ce46: guessed ids is not a true positive
- PASS: ep_7ed3c2e72317ce46: unsupported evidence is not a true positive
- PASS: ep_7ed3c2e72317ce46: wrong currency is not a true positive
- PASS: ep_7ed3c2e72317ce46: amount off by 3 tolerances is not a true positive
- PASS: ep_7ed3c2e72317ce46: wrong type is not a true positive
- PASS: ep_7ed3c2e72317ce46: citing documents by alias keeps full credit
- PASS: ep_7ed3c2e72317ce46: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_7ed3c2e72317ce46: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_7ed3c2e72317ce46: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_7ed3c2e72317ce46: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_7ed3c2e72317ce46: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_7ed3c2e72317ce46: saving steps separates equal answers only slightly
- PASS: ep_5e200627665c3570: correct answer with evidence beats silence
- PASS: ep_5e200627665c3570: repeating findings gains nothing
- PASS: ep_5e200627665c3570: guessed ids is not a true positive
- PASS: ep_5e200627665c3570: unsupported evidence is not a true positive
- PASS: ep_5e200627665c3570: wrong currency is not a true positive
- PASS: ep_5e200627665c3570: amount off by 3 tolerances is not a true positive
- PASS: ep_5e200627665c3570: wrong type is not a true positive
- PASS: ep_5e200627665c3570: citing documents by alias keeps full credit
- PASS: ep_5e200627665c3570: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_5e200627665c3570: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_5e200627665c3570: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_5e200627665c3570: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_5e200627665c3570: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_5e200627665c3570: saving steps separates equal answers only slightly
- PASS: ep_fb48b042a353c95c: correct answer with evidence beats silence
- PASS: ep_fb48b042a353c95c: repeating findings gains nothing
- PASS: ep_fb48b042a353c95c: guessed ids is not a true positive
- PASS: ep_fb48b042a353c95c: unsupported evidence is not a true positive
- PASS: ep_fb48b042a353c95c: wrong currency is not a true positive
- PASS: ep_fb48b042a353c95c: amount off by 3 tolerances is not a true positive
- PASS: ep_fb48b042a353c95c: wrong type is not a true positive
- PASS: ep_fb48b042a353c95c: citing documents by alias keeps full credit
- PASS: ep_fb48b042a353c95c: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_fb48b042a353c95c: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_fb48b042a353c95c: 24 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_fb48b042a353c95c: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_fb48b042a353c95c: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_fb48b042a353c95c: saving steps separates equal answers only slightly
- PASS: ep_6e289b163376cf3f: correct answer with evidence beats silence
- PASS: ep_6e289b163376cf3f: repeating findings gains nothing
- PASS: ep_6e289b163376cf3f: guessed ids is not a true positive
- PASS: ep_6e289b163376cf3f: unsupported evidence is not a true positive
- PASS: ep_6e289b163376cf3f: wrong currency is not a true positive
- PASS: ep_6e289b163376cf3f: amount off by 3 tolerances is not a true positive
- PASS: ep_6e289b163376cf3f: wrong type is not a true positive
- PASS: ep_6e289b163376cf3f: citing documents by alias keeps full credit
- PASS: ep_6e289b163376cf3f: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_6e289b163376cf3f: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_6e289b163376cf3f: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_6e289b163376cf3f: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_6e289b163376cf3f: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_6e289b163376cf3f: saving steps separates equal answers only slightly
- PASS: ep_21bc70af0f5b0d89: correct answer with evidence beats silence
- PASS: ep_21bc70af0f5b0d89: repeating findings gains nothing
- PASS: ep_21bc70af0f5b0d89: guessed ids is not a true positive
- PASS: ep_21bc70af0f5b0d89: unsupported evidence is not a true positive
- PASS: ep_21bc70af0f5b0d89: wrong currency is not a true positive
- PASS: ep_21bc70af0f5b0d89: amount off by 3 tolerances is not a true positive
- PASS: ep_21bc70af0f5b0d89: wrong type is not a true positive
- PASS: ep_21bc70af0f5b0d89: citing documents by alias keeps full credit
- PASS: ep_21bc70af0f5b0d89: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_21bc70af0f5b0d89: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_21bc70af0f5b0d89: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_21bc70af0f5b0d89: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_21bc70af0f5b0d89: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_21bc70af0f5b0d89: saving steps separates equal answers only slightly
- PASS: ep_4df2829e5b915f1b: correct answer with evidence beats silence
- PASS: ep_4df2829e5b915f1b: repeating findings gains nothing
- PASS: ep_4df2829e5b915f1b: guessed ids is not a true positive
- PASS: ep_4df2829e5b915f1b: unsupported evidence is not a true positive
- PASS: ep_4df2829e5b915f1b: wrong currency is not a true positive
- PASS: ep_4df2829e5b915f1b: amount off by 3 tolerances is not a true positive
- PASS: ep_4df2829e5b915f1b: wrong type is not a true positive
- PASS: ep_4df2829e5b915f1b: citing documents by alias keeps full credit
- PASS: ep_4df2829e5b915f1b: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_4df2829e5b915f1b: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_4df2829e5b915f1b: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_4df2829e5b915f1b: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_4df2829e5b915f1b: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_4df2829e5b915f1b: saving steps separates equal answers only slightly
- PASS: ep_e357b07040e21024: correct answer with evidence beats silence
- PASS: ep_e357b07040e21024: repeating findings gains nothing
- PASS: ep_e357b07040e21024: guessed ids is not a true positive
- PASS: ep_e357b07040e21024: unsupported evidence is not a true positive
- PASS: ep_e357b07040e21024: wrong currency is not a true positive
- PASS: ep_e357b07040e21024: amount off by 3 tolerances is not a true positive
- PASS: ep_e357b07040e21024: wrong type is not a true positive
- PASS: ep_e357b07040e21024: citing documents by alias keeps full credit
- PASS: ep_e357b07040e21024: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_e357b07040e21024: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_e357b07040e21024: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_e357b07040e21024: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_e357b07040e21024: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_e357b07040e21024: saving steps separates equal answers only slightly
- PASS: ep_62423f8ee9c1e3d8: correct answer with evidence beats silence
- PASS: ep_62423f8ee9c1e3d8: repeating findings gains nothing
- PASS: ep_62423f8ee9c1e3d8: guessed ids is not a true positive
- PASS: ep_62423f8ee9c1e3d8: unsupported evidence is not a true positive
- PASS: ep_62423f8ee9c1e3d8: wrong currency is not a true positive
- PASS: ep_62423f8ee9c1e3d8: amount off by 3 tolerances is not a true positive
- PASS: ep_62423f8ee9c1e3d8: wrong type is not a true positive
- PASS: ep_62423f8ee9c1e3d8: citing documents by alias keeps full credit
- PASS: ep_62423f8ee9c1e3d8: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_62423f8ee9c1e3d8: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_62423f8ee9c1e3d8: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_62423f8ee9c1e3d8: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_62423f8ee9c1e3d8: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_62423f8ee9c1e3d8: saving steps separates equal answers only slightly
- PASS: ep_bf86a42c4ded774d: correct answer with evidence beats silence
- PASS: ep_bf86a42c4ded774d: repeating findings gains nothing
- PASS: ep_bf86a42c4ded774d: guessed ids is not a true positive
- PASS: ep_bf86a42c4ded774d: unsupported evidence is not a true positive
- PASS: ep_bf86a42c4ded774d: wrong currency is not a true positive
- PASS: ep_bf86a42c4ded774d: amount off by 3 tolerances is not a true positive
- PASS: ep_bf86a42c4ded774d: wrong type is not a true positive
- PASS: ep_bf86a42c4ded774d: citing documents by alias keeps full credit
- PASS: ep_bf86a42c4ded774d: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_bf86a42c4ded774d: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_bf86a42c4ded774d: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_bf86a42c4ded774d: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_bf86a42c4ded774d: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_bf86a42c4ded774d: saving steps separates equal answers only slightly
- PASS: ep_8f0b5dc6a809358d: correct answer with evidence beats silence
- PASS: ep_8f0b5dc6a809358d: repeating findings gains nothing
- PASS: ep_8f0b5dc6a809358d: guessed ids is not a true positive
- PASS: ep_8f0b5dc6a809358d: unsupported evidence is not a true positive
- PASS: ep_8f0b5dc6a809358d: wrong currency is not a true positive
- PASS: ep_8f0b5dc6a809358d: amount off by 3 tolerances is not a true positive
- PASS: ep_8f0b5dc6a809358d: wrong type is not a true positive
- PASS: ep_8f0b5dc6a809358d: citing documents by alias keeps full credit
- PASS: ep_8f0b5dc6a809358d: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_8f0b5dc6a809358d: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_8f0b5dc6a809358d: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_8f0b5dc6a809358d: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_8f0b5dc6a809358d: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_8f0b5dc6a809358d: saving steps separates equal answers only slightly

### 4. Reproducibility (15)

Run time: B_replay 1.3 s, D_paired 16.4 s

#### B_replay (0/8)

- FAIL: dev/auditor: 10 recorded runs, each replays to identical observations and terminal reward (ep_ee223b1157d7e933: reset observation differs; ep_5a13f5014447e4ae: reset observation differs; ep_e02cf9b4701342c8: reset observation differs)
- FAIL: dev/flag_all: 10 recorded runs, each replays to identical observations and terminal reward (ep_ee223b1157d7e933: reset observation differs; ep_5a13f5014447e4ae: reset observation differs; ep_e02cf9b4701342c8: reset observation differs)
- FAIL: dev/random: 10 recorded runs, each replays to identical observations and terminal reward (ep_ee223b1157d7e933: reset observation differs; ep_5a13f5014447e4ae: reset observation differs; ep_e02cf9b4701342c8: reset observation differs)
- FAIL: dev/recon: 10 recorded runs, each replays to identical observations and terminal reward (ep_ee223b1157d7e933: reset observation differs; ep_5a13f5014447e4ae: reset observation differs; ep_e02cf9b4701342c8: reset observation differs)
- FAIL: train/auditor: 10 recorded runs, each replays to identical observations and terminal reward (ep_22fbf4823e039c90: reset observation differs; ep_3814a986d97ec053: reset observation differs; ep_36ad821ac43fc00c: reset observation differs)
- FAIL: train/flag_all: 10 recorded runs, each replays to identical observations and terminal reward (ep_22fbf4823e039c90: reset observation differs; ep_3814a986d97ec053: reset observation differs; ep_36ad821ac43fc00c: reset observation differs)
- FAIL: train/random: 10 recorded runs, each replays to identical observations and terminal reward (ep_22fbf4823e039c90: reset observation differs; ep_3814a986d97ec053: reset observation differs; ep_36ad821ac43fc00c: reset observation differs)
- FAIL: train/recon: 10 recorded runs, each replays to identical observations and terminal reward (ep_22fbf4823e039c90: reset observation differs; ep_3814a986d97ec053: reset observation differs; ep_36ad821ac43fc00c: reset observation differs)

#### D_paired (91/91)

- PASS: h01_clean: same seed and config regenerate identical records and answer key
- PASS: h02_clean: same seed and config regenerate identical records and answer key
- PASS: h03_clean: same seed and config regenerate identical records and answer key
- PASS: h04_clean: same seed and config regenerate identical records and answer key
- PASS: h05_clean: same seed and config regenerate identical records and answer key
- PASS: h06_interacting: same seed and config regenerate identical records and answer key
- PASS: h07_interacting: same seed and config regenerate identical records and answer key
- PASS: h08_interacting: same seed and config regenerate identical records and answer key
- PASS: h09_interacting: same seed and config regenerate identical records and answer key
- PASS: h10_interacting: same seed and config regenerate identical records and answer key
- PASS: h11_mixed: same seed and config regenerate identical records and answer key
- PASS: h12_mixed: same seed and config regenerate identical records and answer key
- PASS: h13_mixed: same seed and config regenerate identical records and answer key
- PASS: h14_mixed: same seed and config regenerate identical records and answer key
- PASS: h15_mixed: same seed and config regenerate identical records and answer key
- PASS: h16_mixed: same seed and config regenerate identical records and answer key
- PASS: h17_mixed: same seed and config regenerate identical records and answer key
- PASS: h18_mixed: same seed and config regenerate identical records and answer key
- PASS: h19_mixed: same seed and config regenerate identical records and answer key
- PASS: h20_mixed: same seed and config regenerate identical records and answer key
- PASS: h02_clean: same actions reproduce transitions and reward (random explorer)
- PASS: h06_interacting: same actions reproduce transitions and reward (random explorer)
- PASS: h13_mixed: same actions reproduce transitions and reward (random explorer)
- PASS: h02_clean: isolated child process and in-process runs are identical
- PASS: h02_clean: isolated child process and in-process runs are identical (recon)
- PASS: h06_interacting: isolated child process and in-process runs are identical
- PASS: h13_mixed: isolated child process and in-process runs are identical
- PASS: h01_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h01_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h01_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h02_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h03_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h04_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h05_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h06_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h07_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h08_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h09_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h10_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h11_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h11_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h11_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h12_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h12_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h12_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h13_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h14_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h14_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h14_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h15_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h15_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h15_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h16_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h16_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h16_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h17_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h17_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h17_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h18_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h18_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h18_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h19_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h19_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h19_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h20_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h20_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed'}: oracle answer and reward preserved
- PASS: h20_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 13}: oracle answer and reward preserved
- PASS: h06_interacting {'remap_seed': 17}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 13}: oracle answer and reward preserved
- PASS: h13_mixed {'remap_seed': 17}: oracle answer and reward preserved

### 5. Engineering and explanation (10)

Run time: A_unit_tests 14.9 s

#### A_unit_tests (1/1)

- PASS: unittest: 145 tests

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.9348 | 0.9348 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 32.6 | 0.0181 | 1.0 | 0.9548 | 0.9281 | 0 | 0.0 |
| hidden_like | flag_all | 20 | -1.0 | -0.9974 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0015 | 3.0 | 0.0054 | 0.0 | -1.0 | -1.0 | 150 | 0.0 |
| hidden_like | oracle | 20 | 1.0 | 1.0 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| hidden_like | random | 20 | -0.8055 | -0.8055 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 | 23.6 | 0.0023 | 0.1 | -0.222 | -1.0 | 5 | 0.0 |
| hidden_like | recon | 20 | -0.49 | -0.49 | 0.1954 | 0.5533 | 0.2126 | 0.7857 | 0.2786 | 0.2786 | 32.6 | 0.006 | 0.0 | -1.0 | -0.32 | 24 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | amount=1, search=55 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | recon | duplicate_invoice=0.7778, unallocated_payment=1.0, wrong_fx_rate=0.7, wrong_period=0.75 | not_flagged=12 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0.9348 | 0.9348 | 0.0 | 1.0 | 1.0 |
| hidden_like | flag_all | -1.0 | -0.9974 | 0.0026 | 0.0 | 0.0015 |
| hidden_like | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| hidden_like | random | -0.8055 | -0.8055 | 0.0 | 0.1 | 0.1 |
| hidden_like | recon | -0.49 | -0.49 | 0.0 | 0.2786 | 0.2786 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0 | - | 23.7143 | 0 / 56 (0.0) | 0 / 222 |
| hidden_like | flag_all | 600 | boundary_doc=10, legit_repeat=17, midnight_fx=5, multi_invoice_payment=14, near_issue=5, overpayment_refund=27, recurring=92, split_payment=14, underpayment=4, unrelated=407, weekend_fx=5 | - | 0 / 56 (0.0) | 0 / 380 |
| hidden_like | oracle | 0 | - | - | - | 222 / 222 |
| hidden_like | random | 24 | boundary_doc=2, legit_repeat=1, near_issue=1, underpayment=1, unrelated=19 | - | 0 / 56 (0.0) | 0 / 74 |
| hidden_like | recon | 163 | boundary_doc=7, legit_repeat=44, midnight_fx=22, multi_invoice_payment=1, near_issue=1, overpayment_refund=33, recurring=2, split_payment=3, underpayment=3, unrelated=47 | 23.7143 | 12 / 56 (0.2143) | 0 / 903 |

