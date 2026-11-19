# auditgym check report

Result: **PASS** in 92 s, version 0.2.0.

Episodes: public master string auditgym-check-v1.

## Checks (grouped by rubric criterion)

### 1. Contract and isolation (25)

Run time: E_leaks 0.4 s

#### E_leaks (3/3)

- PASS: 2179 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

### 2. Data and answer key (25)

Run time: B_committed_episodes 4.1 s, C_data 4.6 s

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
- PASS: h06_interacting verifies (2 issues, 2 attempt(s))
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
- PASS: h19_mixed verifies (4 issues, 2 attempt(s))
- PASS: h20_mixed verifies (5 issues, 1 attempt(s))
- PASS: resampled attempts stay rare (2 over 20 episodes)

### 3. Reward reliability (25)

Run time: C_reward 23.6 s

#### C_reward (248/248)

- PASS: oracle reaches reward 1.0 on all 20 episodes
- PASS: flag-everything attack scores poorly (mean return <= -0.9)
- PASS: scripted auditor closes every episode (no FP, no FN)
- PASS: ordering: oracle > auditor > recon > flag_all
- PASS: ordering on error episodes only: auditor > recon >= flag_all
- PASS: random explorer stays far below the auditor
- PASS: every run finishes inside 100 steps and 60 s
- PASS: no agent process failed
- PASS: ep_d93b7e211400d9fa: silence beats a false accusation on a clean ledger
- PASS: ep_d93b7e211400d9fa: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_d93b7e211400d9fa: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_d93b7e211400d9fa: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_d93b7e211400d9fa: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_d93b7e211400d9fa: saving steps separates equal answers only slightly
- PASS: ep_8a932841ed8e0473: silence beats a false accusation on a clean ledger
- PASS: ep_8a932841ed8e0473: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_8a932841ed8e0473: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_8a932841ed8e0473: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_8a932841ed8e0473: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_8a932841ed8e0473: saving steps separates equal answers only slightly
- PASS: ep_9c4a74074719b6c2: silence beats a false accusation on a clean ledger
- PASS: ep_9c4a74074719b6c2: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_9c4a74074719b6c2: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_9c4a74074719b6c2: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_9c4a74074719b6c2: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_9c4a74074719b6c2: saving steps separates equal answers only slightly
- PASS: ep_d7fb0d8b2dcfc8aa: silence beats a false accusation on a clean ledger
- PASS: ep_d7fb0d8b2dcfc8aa: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_d7fb0d8b2dcfc8aa: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_d7fb0d8b2dcfc8aa: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_d7fb0d8b2dcfc8aa: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_d7fb0d8b2dcfc8aa: saving steps separates equal answers only slightly
- PASS: ep_df671bb159d0fae6: silence beats a false accusation on a clean ledger
- PASS: ep_df671bb159d0fae6: a duplicate_invoice accusation citing a real document scores -1, below silence
- PASS: ep_df671bb159d0fae6: a unallocated_payment accusation citing a real document scores -1, below silence
- PASS: ep_df671bb159d0fae6: a wrong_fx_rate accusation citing a real document scores -1, below silence
- PASS: ep_df671bb159d0fae6: a wrong_period accusation citing a real document scores -1, below silence
- PASS: ep_df671bb159d0fae6: saving steps separates equal answers only slightly
- PASS: ep_99b4722e2dd40466: correct answer with evidence beats silence
- PASS: ep_99b4722e2dd40466: repeating findings gains nothing
- PASS: ep_99b4722e2dd40466: guessed ids is not a true positive
- PASS: ep_99b4722e2dd40466: unsupported evidence is not a true positive
- PASS: ep_99b4722e2dd40466: wrong currency is not a true positive
- PASS: ep_99b4722e2dd40466: amount off by 3 tolerances is not a true positive
- PASS: ep_99b4722e2dd40466: wrong type is not a true positive
- PASS: ep_99b4722e2dd40466: citing documents by alias keeps full credit
- PASS: ep_99b4722e2dd40466: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_99b4722e2dd40466: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_99b4722e2dd40466: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_99b4722e2dd40466: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_99b4722e2dd40466: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_99b4722e2dd40466: saving steps separates equal answers only slightly
- PASS: ep_20f51b55f605db28: correct answer with evidence beats silence
- PASS: ep_20f51b55f605db28: repeating findings gains nothing
- PASS: ep_20f51b55f605db28: guessed ids is not a true positive
- PASS: ep_20f51b55f605db28: unsupported evidence is not a true positive
- PASS: ep_20f51b55f605db28: wrong currency is not a true positive
- PASS: ep_20f51b55f605db28: amount off by 3 tolerances is not a true positive
- PASS: ep_20f51b55f605db28: wrong type is not a true positive
- PASS: ep_20f51b55f605db28: citing documents by alias keeps full credit
- PASS: ep_20f51b55f605db28: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_20f51b55f605db28: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_20f51b55f605db28: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_20f51b55f605db28: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_20f51b55f605db28: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_20f51b55f605db28: saving steps separates equal answers only slightly
- PASS: ep_2283fdaf7538b5aa: correct answer with evidence beats silence
- PASS: ep_2283fdaf7538b5aa: repeating findings gains nothing
- PASS: ep_2283fdaf7538b5aa: guessed ids is not a true positive
- PASS: ep_2283fdaf7538b5aa: unsupported evidence is not a true positive
- PASS: ep_2283fdaf7538b5aa: wrong currency is not a true positive
- PASS: ep_2283fdaf7538b5aa: amount off by 3 tolerances is not a true positive
- PASS: ep_2283fdaf7538b5aa: wrong type is not a true positive
- PASS: ep_2283fdaf7538b5aa: citing documents by alias keeps full credit
- PASS: ep_2283fdaf7538b5aa: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_2283fdaf7538b5aa: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_2283fdaf7538b5aa: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_2283fdaf7538b5aa: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_2283fdaf7538b5aa: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_2283fdaf7538b5aa: saving steps separates equal answers only slightly
- PASS: ep_9a062e8ef70c2867: correct answer with evidence beats silence
- PASS: ep_9a062e8ef70c2867: repeating findings gains nothing
- PASS: ep_9a062e8ef70c2867: guessed ids is not a true positive
- PASS: ep_9a062e8ef70c2867: unsupported evidence is not a true positive
- PASS: ep_9a062e8ef70c2867: wrong currency is not a true positive
- PASS: ep_9a062e8ef70c2867: amount off by 3 tolerances is not a true positive
- PASS: ep_9a062e8ef70c2867: wrong type is not a true positive
- PASS: ep_9a062e8ef70c2867: citing documents by alias keeps full credit
- PASS: ep_9a062e8ef70c2867: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_9a062e8ef70c2867: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_9a062e8ef70c2867: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_9a062e8ef70c2867: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_9a062e8ef70c2867: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_9a062e8ef70c2867: saving steps separates equal answers only slightly
- PASS: ep_2c65039c6d33d0d2: correct answer with evidence beats silence
- PASS: ep_2c65039c6d33d0d2: repeating findings gains nothing
- PASS: ep_2c65039c6d33d0d2: guessed ids is not a true positive
- PASS: ep_2c65039c6d33d0d2: unsupported evidence is not a true positive
- PASS: ep_2c65039c6d33d0d2: wrong currency is not a true positive
- PASS: ep_2c65039c6d33d0d2: amount off by 3 tolerances is not a true positive
- PASS: ep_2c65039c6d33d0d2: wrong type is not a true positive
- PASS: ep_2c65039c6d33d0d2: citing documents by alias keeps full credit
- PASS: ep_2c65039c6d33d0d2: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_2c65039c6d33d0d2: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_2c65039c6d33d0d2: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_2c65039c6d33d0d2: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_2c65039c6d33d0d2: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_2c65039c6d33d0d2: saving steps separates equal answers only slightly
- PASS: ep_8bd01b41a1157577: correct answer with evidence beats silence
- PASS: ep_8bd01b41a1157577: repeating findings gains nothing
- PASS: ep_8bd01b41a1157577: guessed ids is not a true positive
- PASS: ep_8bd01b41a1157577: unsupported evidence is not a true positive
- PASS: ep_8bd01b41a1157577: wrong currency is not a true positive
- PASS: ep_8bd01b41a1157577: amount off by 3 tolerances is not a true positive
- PASS: ep_8bd01b41a1157577: wrong type is not a true positive
- PASS: ep_8bd01b41a1157577: citing documents by alias keeps full credit
- PASS: ep_8bd01b41a1157577: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_8bd01b41a1157577: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_8bd01b41a1157577: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_8bd01b41a1157577: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_8bd01b41a1157577: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_8bd01b41a1157577: saving steps separates equal answers only slightly
- PASS: ep_f7db93a8c32a772c: correct answer with evidence beats silence
- PASS: ep_f7db93a8c32a772c: repeating findings gains nothing
- PASS: ep_f7db93a8c32a772c: guessed ids is not a true positive
- PASS: ep_f7db93a8c32a772c: unsupported evidence is not a true positive
- PASS: ep_f7db93a8c32a772c: wrong currency is not a true positive
- PASS: ep_f7db93a8c32a772c: amount off by 3 tolerances is not a true positive
- PASS: ep_f7db93a8c32a772c: wrong type is not a true positive
- PASS: ep_f7db93a8c32a772c: citing documents by alias keeps full credit
- PASS: ep_f7db93a8c32a772c: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_f7db93a8c32a772c: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_f7db93a8c32a772c: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_f7db93a8c32a772c: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_f7db93a8c32a772c: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_f7db93a8c32a772c: saving steps separates equal answers only slightly
- PASS: ep_b1e37228bd7ef0a1: correct answer with evidence beats silence
- PASS: ep_b1e37228bd7ef0a1: repeating findings gains nothing
- PASS: ep_b1e37228bd7ef0a1: guessed ids is not a true positive
- PASS: ep_b1e37228bd7ef0a1: unsupported evidence is not a true positive
- PASS: ep_b1e37228bd7ef0a1: wrong currency is not a true positive
- PASS: ep_b1e37228bd7ef0a1: amount off by 3 tolerances is not a true positive
- PASS: ep_b1e37228bd7ef0a1: wrong type is not a true positive
- PASS: ep_b1e37228bd7ef0a1: citing documents by alias keeps full credit
- PASS: ep_b1e37228bd7ef0a1: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_b1e37228bd7ef0a1: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_b1e37228bd7ef0a1: 24 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_b1e37228bd7ef0a1: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_b1e37228bd7ef0a1: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_b1e37228bd7ef0a1: saving steps separates equal answers only slightly
- PASS: ep_ee09d07dfa0f5602: correct answer with evidence beats silence
- PASS: ep_ee09d07dfa0f5602: repeating findings gains nothing
- PASS: ep_ee09d07dfa0f5602: guessed ids is not a true positive
- PASS: ep_ee09d07dfa0f5602: unsupported evidence is not a true positive
- PASS: ep_ee09d07dfa0f5602: wrong currency is not a true positive
- PASS: ep_ee09d07dfa0f5602: amount off by 3 tolerances is not a true positive
- PASS: ep_ee09d07dfa0f5602: wrong type is not a true positive
- PASS: ep_ee09d07dfa0f5602: citing documents by alias keeps full credit
- PASS: ep_ee09d07dfa0f5602: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_ee09d07dfa0f5602: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_ee09d07dfa0f5602: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_ee09d07dfa0f5602: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_ee09d07dfa0f5602: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_ee09d07dfa0f5602: saving steps separates equal answers only slightly
- PASS: ep_fa7ed03738cd200a: correct answer with evidence beats silence
- PASS: ep_fa7ed03738cd200a: repeating findings gains nothing
- PASS: ep_fa7ed03738cd200a: guessed ids is not a true positive
- PASS: ep_fa7ed03738cd200a: unsupported evidence is not a true positive
- PASS: ep_fa7ed03738cd200a: wrong currency is not a true positive
- PASS: ep_fa7ed03738cd200a: amount off by 3 tolerances is not a true positive
- PASS: ep_fa7ed03738cd200a: wrong type is not a true positive
- PASS: ep_fa7ed03738cd200a: citing documents by alias keeps full credit
- PASS: ep_fa7ed03738cd200a: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_fa7ed03738cd200a: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_fa7ed03738cd200a: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_fa7ed03738cd200a: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_fa7ed03738cd200a: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_fa7ed03738cd200a: saving steps separates equal answers only slightly
- PASS: ep_7c5ece92fbe0fa8b: correct answer with evidence beats silence
- PASS: ep_7c5ece92fbe0fa8b: repeating findings gains nothing
- PASS: ep_7c5ece92fbe0fa8b: guessed ids is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: unsupported evidence is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: wrong currency is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: amount off by 3 tolerances is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: wrong type is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: citing documents by alias keeps full credit
- PASS: ep_7c5ece92fbe0fa8b: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_7c5ece92fbe0fa8b: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_7c5ece92fbe0fa8b: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_7c5ece92fbe0fa8b: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_7c5ece92fbe0fa8b: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_7c5ece92fbe0fa8b: saving steps separates equal answers only slightly
- PASS: ep_b670bf113ecbdef0: correct answer with evidence beats silence
- PASS: ep_b670bf113ecbdef0: repeating findings gains nothing
- PASS: ep_b670bf113ecbdef0: guessed ids is not a true positive
- PASS: ep_b670bf113ecbdef0: unsupported evidence is not a true positive
- PASS: ep_b670bf113ecbdef0: wrong currency is not a true positive
- PASS: ep_b670bf113ecbdef0: amount off by 3 tolerances is not a true positive
- PASS: ep_b670bf113ecbdef0: wrong type is not a true positive
- PASS: ep_b670bf113ecbdef0: citing documents by alias keeps full credit
- PASS: ep_b670bf113ecbdef0: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_b670bf113ecbdef0: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_b670bf113ecbdef0: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_b670bf113ecbdef0: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_b670bf113ecbdef0: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_b670bf113ecbdef0: saving steps separates equal answers only slightly
- PASS: ep_d9f41ef85b1239f6: correct answer with evidence beats silence
- PASS: ep_d9f41ef85b1239f6: repeating findings gains nothing
- PASS: ep_d9f41ef85b1239f6: guessed ids is not a true positive
- PASS: ep_d9f41ef85b1239f6: unsupported evidence is not a true positive
- PASS: ep_d9f41ef85b1239f6: wrong currency is not a true positive
- PASS: ep_d9f41ef85b1239f6: amount off by 3 tolerances is not a true positive
- PASS: ep_d9f41ef85b1239f6: wrong type is not a true positive
- PASS: ep_d9f41ef85b1239f6: citing documents by alias keeps full credit
- PASS: ep_d9f41ef85b1239f6: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_d9f41ef85b1239f6: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_d9f41ef85b1239f6: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_d9f41ef85b1239f6: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_d9f41ef85b1239f6: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_d9f41ef85b1239f6: saving steps separates equal answers only slightly
- PASS: ep_9f209e44c05ddb1a: correct answer with evidence beats silence
- PASS: ep_9f209e44c05ddb1a: repeating findings gains nothing
- PASS: ep_9f209e44c05ddb1a: guessed ids is not a true positive
- PASS: ep_9f209e44c05ddb1a: unsupported evidence is not a true positive
- PASS: ep_9f209e44c05ddb1a: wrong currency is not a true positive
- PASS: ep_9f209e44c05ddb1a: amount off by 3 tolerances is not a true positive
- PASS: ep_9f209e44c05ddb1a: wrong type is not a true positive
- PASS: ep_9f209e44c05ddb1a: citing documents by alias keeps full credit
- PASS: ep_9f209e44c05ddb1a: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_9f209e44c05ddb1a: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_9f209e44c05ddb1a: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_9f209e44c05ddb1a: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_9f209e44c05ddb1a: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_9f209e44c05ddb1a: saving steps separates equal answers only slightly
- PASS: ep_3c13484c7cf31a46: correct answer with evidence beats silence
- PASS: ep_3c13484c7cf31a46: repeating findings gains nothing
- PASS: ep_3c13484c7cf31a46: guessed ids is not a true positive
- PASS: ep_3c13484c7cf31a46: unsupported evidence is not a true positive
- PASS: ep_3c13484c7cf31a46: wrong currency is not a true positive
- PASS: ep_3c13484c7cf31a46: amount off by 3 tolerances is not a true positive
- PASS: ep_3c13484c7cf31a46: wrong type is not a true positive
- PASS: ep_3c13484c7cf31a46: citing documents by alias keeps full credit
- PASS: ep_3c13484c7cf31a46: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_3c13484c7cf31a46: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_3c13484c7cf31a46: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_3c13484c7cf31a46: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_3c13484c7cf31a46: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_3c13484c7cf31a46: saving steps separates equal answers only slightly

### 4. Reproducibility (15)

Run time: B_replay 1.4 s, D_paired 17.3 s

#### B_replay (8/8)

- PASS: dev/auditor: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/flag_all: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/random: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/recon: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/auditor: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/flag_all: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/random: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/recon: 10 recorded runs, each replays to identical observations and terminal reward

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

Run time: A_unit_tests 41.1 s

#### A_unit_tests (1/1)

- PASS: unittest: 189 tests

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.936 | 0.936 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 32.0 | 0.0125 | 1.0 | 0.9532 | 0.9303 | 0 | 0.0 |
| hidden_like | flag_all | 20 | -1.0 | -0.9946 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.003 | 3.0 | 0.0031 | 0.0 | -1.0 | -1.0 | 150 | 0.0 |
| hidden_like | oracle | 20 | 1.0 | 1.0 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| hidden_like | random | 20 | -0.6132 | -0.6132 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2 | 0.2 | 33.95 | 0.004 | 0.2 | 0.5472 | -1.0 | 2 | 0.0 |
| hidden_like | recon | 20 | -0.5887 | -0.5887 | 0.1501 | 0.5425 | 0.1634 | 0.75 | 0.2307 | 0.2307 | 32.0 | 0.007 | 0.0 | -1.0 | -0.4516 | 40 | 0.0 |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | amount=2, search=54 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | not_flagged=1, search=55 |
| hidden_like | recon | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=0.6, wrong_period=0.625 | not_flagged=14 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0.936 | 0.936 | 0.0 | 1.0 | 1.0 |
| hidden_like | flag_all | -1.0 | -0.9946 | 0.0054 | 0.0 | 0.003 |
| hidden_like | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| hidden_like | random | -0.6132 | -0.6132 | 0.0 | 0.2 | 0.2 |
| hidden_like | recon | -0.5887 | -0.5887 | 0.0 | 0.2307 | 0.2307 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0 | - | 21.0536 | 0 / 56 (0.0) | 0 / 222 |
| hidden_like | flag_all | 600 | boundary_doc=25, legit_repeat=11, multi_invoice_payment=14, near_issue=17, overpayment_refund=5, recurring=113, split_payment=5, underpayment=23, unrelated=378, weekend_fx=9 | - | 0 / 56 (0.0) | 0 / 380 |
| hidden_like | oracle | 0 | - | - | - | 222 / 222 |
| hidden_like | random | 25 | boundary_doc=2, legit_repeat=1, multi_invoice_payment=1, null_ref_receipt=1, overpayment_refund=3, split_payment=1, unrelated=16 | 48.0 | 1 / 56 (0.0179) | 0 / 97 |
| hidden_like | recon | 215 | boundary_doc=34, legit_repeat=45, midnight_fx=25, multi_invoice_payment=2, near_issue=1, overpayment_refund=30, recurring=6, split_payment=2, underpayment=6, unrelated=64 | 21.0536 | 14 / 56 (0.25) | 0 / 1091 |

