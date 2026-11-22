# auditgym check report

Result: **PASS** in 239 s, version 0.4.0.

Episodes: public master string auditgym-check-v1.

Policy isolation: separate user (uid 10002).

Code: code 088761e7a860673fd91718f7a2be562dad052be26de40bf5c6390369e80d363d (60 files), Python 3.11.10, Linux-7.0.0-1020-azure-x86_64-with-glibc2.36.

Coverage: 697 named checks of 83 kinds (a kind is one property; most run on every episode they apply to).

## Checks (grouped by rubric criterion)

### 1. Contract and isolation (25)

Run time: F_contract 0.0 s, E_leaks 0.2 s

#### F_contract (20/20)

- PASS: ep_47d65a6da3a8d4ad: reset returns exactly task, manifest, policy and remaining_steps
- PASS: ep_47d65a6da3a8d4ad: every later observation has only result, error and remaining_steps
- PASS: ep_47d65a6da3a8d4ad: a page holds at most 50 rows and paging reaches every row once, in order (ledger)
- PASS: ep_47d65a6da3a8d4ad: the cursor is stable: the same cursor returns the same page, also in a fresh environment
- PASS: ep_47d65a6da3a8d4ad: a page limit above the maximum is refused with a bounded error
- PASS: ep_47d65a6da3a8d4ad: an unknown ID gives a bounded error and spends a step
- PASS: ep_47d65a6da3a8d4ad: an unknown action gives a bounded error and spends a step
- PASS: ep_47d65a6da3a8d4ad: the calculator evaluates a valid expression
- PASS: ep_47d65a6da3a8d4ad: the calculator rejects __import__('os')
- PASS: ep_47d65a6da3a8d4ad: the calculator rejects 2**8
- PASS: ep_47d65a6da3a8d4ad: the calculator rejects 1/0
- PASS: ep_47d65a6da3a8d4ad: after submit the episode is finished and further steps change nothing
- PASS: ep_47d65a6da3a8d4ad: at step 100 (not before) the episode truncates with an empty answer
- PASS: ep_47d65a6da3a8d4ad: the time limit on a frozen clock truncates with an empty answer
- PASS: ep_47d65a6da3a8d4ad: eval mode returns reward 0 on every step, including the last
- PASS: ep_47d65a6da3a8d4ad: info carries only episode_id in eval mode, also at the end
- PASS: ep_47d65a6da3a8d4ad: an invalid submission scores -1
- PASS: ep_47d65a6da3a8d4ad: a foreign episode_id scores -1
- PASS: ep_47d65a6da3a8d4ad: all 10 sampled observations validate against observation.schema.json
- PASS: ep_47d65a6da3a8d4ad: seeded contract fuzz (300 actions, reset every episode end) has 0 invariant violations

#### E_leaks (3/3)

- PASS: 2089 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

### 2. Data and answer key (25)

Run time: B_committed_episodes 1.9 s, C_data 2.1 s

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

#### C_data (22/22)

- PASS: h01_clean verifies (0 issues, 2 attempt(s))
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
- PASS: h12_mixed verifies (4 issues, 2 attempt(s))
- PASS: h13_mixed verifies (6 issues, 1 attempt(s))
- PASS: h14_mixed verifies (3 issues, 1 attempt(s))
- PASS: h15_mixed verifies (4 issues, 1 attempt(s))
- PASS: h16_mixed verifies (5 issues, 1 attempt(s))
- PASS: h17_mixed verifies (2 issues, 1 attempt(s))
- PASS: h18_mixed verifies (3 issues, 1 attempt(s))
- PASS: h19_mixed verifies (4 issues, 2 attempt(s))
- PASS: h20_mixed verifies (5 issues, 1 attempt(s))
- PASS: sampling resamples (SampleRetry, BooksError or a sampling check) stay rare (3 over 20 episodes)
- PASS: no candidate episode was rejected by a correctness check (3 resampled, all for sampling reasons)

### 3. Reward reliability (25)

Run time: C_reward 19.5 s

#### C_reward (468/468)

- PASS: oracle reaches reward 1.0 on all 20 episodes
- PASS: flag-everything attack scores poorly (mean return <= -0.9)
- PASS: scripted auditor closes every episode (no FP, no FN)
- PASS: ordering: oracle > auditor > recon > flag_all
- PASS: ordering on error episodes only: auditor > recon >= flag_all
- PASS: random explorer stays far below the auditor
- PASS: ordering: auditor > silent
- PASS: every run finishes inside 100 steps and 60 s
- PASS: no agent process failed
- PASS: ep_246d30ec6c013247: silence beats a false accusation on a clean ledger
- PASS: ep_246d30ec6c013247: 3 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 3 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 1 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 7 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 2 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: 16 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_246d30ec6c013247: saving steps separates equal answers only slightly
- PASS: ep_64f9b5b7d0795025: silence beats a false accusation on a clean ledger
- PASS: ep_64f9b5b7d0795025: 5 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 1 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 4 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 5 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 7 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 3 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: 30 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_64f9b5b7d0795025: saving steps separates equal answers only slightly
- PASS: ep_a440890457b68488: silence beats a false accusation on a clean ledger
- PASS: ep_a440890457b68488: 6 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 3 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 5 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 2 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 3 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 2 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 3 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 4 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 12 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 4 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 3 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: 29 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_a440890457b68488: saving steps separates equal answers only slightly
- PASS: ep_f27513fc59411601: silence beats a false accusation on a clean ledger
- PASS: ep_f27513fc59411601: 2 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 5 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 7 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 2 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: 15 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f27513fc59411601: saving steps separates equal answers only slightly
- PASS: ep_d4638527facc7e14: silence beats a false accusation on a clean ledger
- PASS: ep_d4638527facc7e14: 5 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 3 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 5 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 3 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: 33 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_d4638527facc7e14: saving steps separates equal answers only slightly
- PASS: ep_47d65a6da3a8d4ad: correct answer with evidence beats silence
- PASS: ep_47d65a6da3a8d4ad: repeating findings gains nothing
- PASS: ep_47d65a6da3a8d4ad: guessed ids is not a true positive
- PASS: ep_47d65a6da3a8d4ad: unsupported evidence is not a true positive
- PASS: ep_47d65a6da3a8d4ad: wrong currency is not a true positive
- PASS: ep_47d65a6da3a8d4ad: amount off by 3 tolerances is not a true positive
- PASS: ep_47d65a6da3a8d4ad: wrong type is not a true positive
- PASS: ep_47d65a6da3a8d4ad: citing documents by alias keeps full credit
- PASS: ep_47d65a6da3a8d4ad: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_47d65a6da3a8d4ad: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_47d65a6da3a8d4ad: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_47d65a6da3a8d4ad: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_47d65a6da3a8d4ad: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_47d65a6da3a8d4ad: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 8 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: 28 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_47d65a6da3a8d4ad: saving steps separates equal answers only slightly
- PASS: ep_7bdf200f1642db5a: correct answer with evidence beats silence
- PASS: ep_7bdf200f1642db5a: repeating findings gains nothing
- PASS: ep_7bdf200f1642db5a: guessed ids is not a true positive
- PASS: ep_7bdf200f1642db5a: unsupported evidence is not a true positive
- PASS: ep_7bdf200f1642db5a: wrong currency is not a true positive
- PASS: ep_7bdf200f1642db5a: amount off by 3 tolerances is not a true positive
- PASS: ep_7bdf200f1642db5a: wrong type is not a true positive
- PASS: ep_7bdf200f1642db5a: citing documents by alias keeps full credit
- PASS: ep_7bdf200f1642db5a: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_7bdf200f1642db5a: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_7bdf200f1642db5a: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_7bdf200f1642db5a: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_7bdf200f1642db5a: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_7bdf200f1642db5a: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 9 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 7 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: 44 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_7bdf200f1642db5a: saving steps separates equal answers only slightly
- PASS: ep_3121f32838090bda: correct answer with evidence beats silence
- PASS: ep_3121f32838090bda: repeating findings gains nothing
- PASS: ep_3121f32838090bda: guessed ids is not a true positive
- PASS: ep_3121f32838090bda: unsupported evidence is not a true positive
- PASS: ep_3121f32838090bda: wrong currency is not a true positive
- PASS: ep_3121f32838090bda: amount off by 3 tolerances is not a true positive
- PASS: ep_3121f32838090bda: wrong type is not a true positive
- PASS: ep_3121f32838090bda: citing documents by alias keeps full credit
- PASS: ep_3121f32838090bda: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_3121f32838090bda: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_3121f32838090bda: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_3121f32838090bda: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_3121f32838090bda: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_3121f32838090bda: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 2 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 1 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 2 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: 13 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_3121f32838090bda: saving steps separates equal answers only slightly
- PASS: ep_41a1c2e49f27c335: correct answer with evidence beats silence
- PASS: ep_41a1c2e49f27c335: repeating findings gains nothing
- PASS: ep_41a1c2e49f27c335: guessed ids is not a true positive
- PASS: ep_41a1c2e49f27c335: unsupported evidence is not a true positive
- PASS: ep_41a1c2e49f27c335: wrong currency is not a true positive
- PASS: ep_41a1c2e49f27c335: amount off by 3 tolerances is not a true positive
- PASS: ep_41a1c2e49f27c335: wrong type is not a true positive
- PASS: ep_41a1c2e49f27c335: citing documents by alias keeps full credit
- PASS: ep_41a1c2e49f27c335: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_41a1c2e49f27c335: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_41a1c2e49f27c335: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_41a1c2e49f27c335: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_41a1c2e49f27c335: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_41a1c2e49f27c335: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: 25 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_41a1c2e49f27c335: saving steps separates equal answers only slightly
- PASS: ep_0316288cdafe6200: correct answer with evidence beats silence
- PASS: ep_0316288cdafe6200: repeating findings gains nothing
- PASS: ep_0316288cdafe6200: guessed ids is not a true positive
- PASS: ep_0316288cdafe6200: unsupported evidence is not a true positive
- PASS: ep_0316288cdafe6200: wrong currency is not a true positive
- PASS: ep_0316288cdafe6200: amount off by 3 tolerances is not a true positive
- PASS: ep_0316288cdafe6200: wrong type is not a true positive
- PASS: ep_0316288cdafe6200: citing documents by alias keeps full credit
- PASS: ep_0316288cdafe6200: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_0316288cdafe6200: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_0316288cdafe6200: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_0316288cdafe6200: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_0316288cdafe6200: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_0316288cdafe6200: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 8 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: 38 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_0316288cdafe6200: saving steps separates equal answers only slightly
- PASS: ep_932585a5673f7be6: correct answer with evidence beats silence
- PASS: ep_932585a5673f7be6: repeating findings gains nothing
- PASS: ep_932585a5673f7be6: guessed ids is not a true positive
- PASS: ep_932585a5673f7be6: unsupported evidence is not a true positive
- PASS: ep_932585a5673f7be6: wrong currency is not a true positive
- PASS: ep_932585a5673f7be6: amount off by 3 tolerances is not a true positive
- PASS: ep_932585a5673f7be6: wrong type is not a true positive
- PASS: ep_932585a5673f7be6: citing documents by alias keeps full credit
- PASS: ep_932585a5673f7be6: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_932585a5673f7be6: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_932585a5673f7be6: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_932585a5673f7be6: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_932585a5673f7be6: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_932585a5673f7be6: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 9 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: 33 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_932585a5673f7be6: saving steps separates equal answers only slightly
- PASS: ep_32d76d1530a9f2e6: correct answer with evidence beats silence
- PASS: ep_32d76d1530a9f2e6: repeating findings gains nothing
- PASS: ep_32d76d1530a9f2e6: guessed ids is not a true positive
- PASS: ep_32d76d1530a9f2e6: unsupported evidence is not a true positive
- PASS: ep_32d76d1530a9f2e6: wrong currency is not a true positive
- PASS: ep_32d76d1530a9f2e6: amount off by 3 tolerances is not a true positive
- PASS: ep_32d76d1530a9f2e6: wrong type is not a true positive
- PASS: ep_32d76d1530a9f2e6: citing documents by alias keeps full credit
- PASS: ep_32d76d1530a9f2e6: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_32d76d1530a9f2e6: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_32d76d1530a9f2e6: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_32d76d1530a9f2e6: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_32d76d1530a9f2e6: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_32d76d1530a9f2e6: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: 19 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_32d76d1530a9f2e6: saving steps separates equal answers only slightly
- PASS: ep_73fb7991086b4580: correct answer with evidence beats silence
- PASS: ep_73fb7991086b4580: repeating findings gains nothing
- PASS: ep_73fb7991086b4580: guessed ids is not a true positive
- PASS: ep_73fb7991086b4580: unsupported evidence is not a true positive
- PASS: ep_73fb7991086b4580: wrong currency is not a true positive
- PASS: ep_73fb7991086b4580: amount off by 3 tolerances is not a true positive
- PASS: ep_73fb7991086b4580: wrong type is not a true positive
- PASS: ep_73fb7991086b4580: citing documents by alias keeps full credit
- PASS: ep_73fb7991086b4580: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_73fb7991086b4580: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_73fb7991086b4580: 24 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_73fb7991086b4580: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_73fb7991086b4580: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_73fb7991086b4580: 1 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 4 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 2 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: 8 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_73fb7991086b4580: saving steps separates equal answers only slightly
- PASS: ep_86fbb4292cb21eff: correct answer with evidence beats silence
- PASS: ep_86fbb4292cb21eff: repeating findings gains nothing
- PASS: ep_86fbb4292cb21eff: guessed ids is not a true positive
- PASS: ep_86fbb4292cb21eff: unsupported evidence is not a true positive
- PASS: ep_86fbb4292cb21eff: wrong currency is not a true positive
- PASS: ep_86fbb4292cb21eff: amount off by 3 tolerances is not a true positive
- PASS: ep_86fbb4292cb21eff: wrong type is not a true positive
- PASS: ep_86fbb4292cb21eff: citing documents by alias keeps full credit
- PASS: ep_86fbb4292cb21eff: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_86fbb4292cb21eff: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_86fbb4292cb21eff: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_86fbb4292cb21eff: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_86fbb4292cb21eff: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_86fbb4292cb21eff: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: 30 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_86fbb4292cb21eff: saving steps separates equal answers only slightly
- PASS: ep_8a75ee87b2b417f0: correct answer with evidence beats silence
- PASS: ep_8a75ee87b2b417f0: repeating findings gains nothing
- PASS: ep_8a75ee87b2b417f0: guessed ids is not a true positive
- PASS: ep_8a75ee87b2b417f0: unsupported evidence is not a true positive
- PASS: ep_8a75ee87b2b417f0: wrong currency is not a true positive
- PASS: ep_8a75ee87b2b417f0: amount off by 3 tolerances is not a true positive
- PASS: ep_8a75ee87b2b417f0: wrong type is not a true positive
- PASS: ep_8a75ee87b2b417f0: citing documents by alias keeps full credit
- PASS: ep_8a75ee87b2b417f0: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_8a75ee87b2b417f0: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_8a75ee87b2b417f0: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_8a75ee87b2b417f0: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_8a75ee87b2b417f0: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_8a75ee87b2b417f0: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 13 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: 37 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8a75ee87b2b417f0: saving steps separates equal answers only slightly
- PASS: ep_a661f328eb0b8e1f: correct answer with evidence beats silence
- PASS: ep_a661f328eb0b8e1f: repeating findings gains nothing
- PASS: ep_a661f328eb0b8e1f: guessed ids is not a true positive
- PASS: ep_a661f328eb0b8e1f: unsupported evidence is not a true positive
- PASS: ep_a661f328eb0b8e1f: wrong currency is not a true positive
- PASS: ep_a661f328eb0b8e1f: amount off by 3 tolerances is not a true positive
- PASS: ep_a661f328eb0b8e1f: wrong type is not a true positive
- PASS: ep_a661f328eb0b8e1f: citing documents by alias keeps full credit
- PASS: ep_a661f328eb0b8e1f: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_a661f328eb0b8e1f: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_a661f328eb0b8e1f: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_a661f328eb0b8e1f: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_a661f328eb0b8e1f: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_a661f328eb0b8e1f: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 9 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: 43 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_a661f328eb0b8e1f: saving steps separates equal answers only slightly
- PASS: ep_2a1ad532de9525dc: correct answer with evidence beats silence
- PASS: ep_2a1ad532de9525dc: repeating findings gains nothing
- PASS: ep_2a1ad532de9525dc: guessed ids is not a true positive
- PASS: ep_2a1ad532de9525dc: unsupported evidence is not a true positive
- PASS: ep_2a1ad532de9525dc: wrong currency is not a true positive
- PASS: ep_2a1ad532de9525dc: amount off by 3 tolerances is not a true positive
- PASS: ep_2a1ad532de9525dc: wrong type is not a true positive
- PASS: ep_2a1ad532de9525dc: citing documents by alias keeps full credit
- PASS: ep_2a1ad532de9525dc: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_2a1ad532de9525dc: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_2a1ad532de9525dc: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_2a1ad532de9525dc: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_2a1ad532de9525dc: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_2a1ad532de9525dc: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 9 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: 46 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2a1ad532de9525dc: saving steps separates equal answers only slightly
- PASS: ep_b8290c0bdc13231f: correct answer with evidence beats silence
- PASS: ep_b8290c0bdc13231f: repeating findings gains nothing
- PASS: ep_b8290c0bdc13231f: guessed ids is not a true positive
- PASS: ep_b8290c0bdc13231f: unsupported evidence is not a true positive
- PASS: ep_b8290c0bdc13231f: wrong currency is not a true positive
- PASS: ep_b8290c0bdc13231f: amount off by 3 tolerances is not a true positive
- PASS: ep_b8290c0bdc13231f: wrong type is not a true positive
- PASS: ep_b8290c0bdc13231f: citing documents by alias keeps full credit
- PASS: ep_b8290c0bdc13231f: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_b8290c0bdc13231f: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_b8290c0bdc13231f: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_b8290c0bdc13231f: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_b8290c0bdc13231f: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_b8290c0bdc13231f: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: 31 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_b8290c0bdc13231f: saving steps separates equal answers only slightly
- PASS: ep_de4c3d331f6ab09f: correct answer with evidence beats silence
- PASS: ep_de4c3d331f6ab09f: repeating findings gains nothing
- PASS: ep_de4c3d331f6ab09f: guessed ids is not a true positive
- PASS: ep_de4c3d331f6ab09f: unsupported evidence is not a true positive
- PASS: ep_de4c3d331f6ab09f: wrong currency is not a true positive
- PASS: ep_de4c3d331f6ab09f: amount off by 3 tolerances is not a true positive
- PASS: ep_de4c3d331f6ab09f: wrong type is not a true positive
- PASS: ep_de4c3d331f6ab09f: citing documents by alias keeps full credit
- PASS: ep_de4c3d331f6ab09f: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_de4c3d331f6ab09f: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_de4c3d331f6ab09f: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_de4c3d331f6ab09f: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_de4c3d331f6ab09f: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_de4c3d331f6ab09f: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 8 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 9 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: 30 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_de4c3d331f6ab09f: saving steps separates equal answers only slightly
- PASS: ep_81239a83867a382e: correct answer with evidence beats silence
- PASS: ep_81239a83867a382e: repeating findings gains nothing
- PASS: ep_81239a83867a382e: guessed ids is not a true positive
- PASS: ep_81239a83867a382e: unsupported evidence is not a true positive
- PASS: ep_81239a83867a382e: wrong currency is not a true positive
- PASS: ep_81239a83867a382e: amount off by 3 tolerances is not a true positive
- PASS: ep_81239a83867a382e: wrong type is not a true positive
- PASS: ep_81239a83867a382e: citing documents by alias keeps full credit
- PASS: ep_81239a83867a382e: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_81239a83867a382e: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_81239a83867a382e: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_81239a83867a382e: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_81239a83867a382e: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_81239a83867a382e: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 9 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 9 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: 36 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_81239a83867a382e: saving steps separates equal answers only slightly

### 4. Reproducibility (15)

Run time: B_replay 0.6 s, D_paired 14.5 s

#### B_replay (10/10)

- PASS: dev/auditor: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/flag_all: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/random: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/recon: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: dev/silent: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/auditor: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/flag_all: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/random: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/recon: 10 recorded runs, each replays to identical observations and terminal reward
- PASS: train/silent: 10 recorded runs, each replays to identical observations and terminal reward

#### D_paired (133/133)

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
- PASS: h01_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h01_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h01_clean {'shift_years': 28}: oracle answer and reward preserved
- PASS: h01_clean {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h02_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h02_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h02_clean {'shift_years': 28}: oracle answer and reward preserved
- PASS: h02_clean {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h03_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h03_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h03_clean {'shift_years': 28}: oracle answer and reward preserved
- PASS: h03_clean {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h04_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h04_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h04_clean {'shift_years': 28}: oracle answer and reward preserved
- PASS: h04_clean {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h05_clean {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h05_clean {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h05_clean {'shift_years': 28}: oracle answer and reward preserved
- PASS: h05_clean {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h06_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h06_interacting {'shift_years': 28}: oracle answer and reward preserved
- PASS: h06_interacting {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h07_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h07_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h07_interacting {'shift_years': 28}: oracle answer and reward preserved
- PASS: h07_interacting {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h08_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h08_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h08_interacting {'shift_years': 28}: oracle answer and reward preserved
- PASS: h08_interacting {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h09_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h09_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h09_interacting {'shift_years': 28}: oracle answer and reward preserved
- PASS: h09_interacting {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h10_interacting {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h10_interacting {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h10_interacting {'shift_years': 28}: oracle answer and reward preserved
- PASS: h10_interacting {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h11_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h11_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h11_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h11_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h11_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h12_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h12_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h12_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h12_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h12_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h13_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h13_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h13_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h14_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h14_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h14_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h14_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h14_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h15_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h15_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h15_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h15_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h15_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h16_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h16_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h16_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h16_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h16_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h17_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h17_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h17_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h17_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h17_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h18_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h18_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h18_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h18_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h18_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h19_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h19_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h19_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h19_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h19_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h20_mixed {'permute_seed': 11, 'remap_seed': 5}: oracle answer and reward preserved
- PASS: h20_mixed {'permute_seed': 7, 'remap_seed': 9, 'ts_repr': 'mixed', 'rename_seed': 21}: oracle answer and reward preserved
- PASS: h20_mixed {'remap_seed': 3, 'ts_repr': 'utc'}: oracle answer and reward preserved
- PASS: h20_mixed {'shift_years': 28}: oracle answer and reward preserved
- PASS: h20_mixed {'shift_years': 28, 'permute_seed': 4, 'remap_seed': 6, 'ts_repr': 'local', 'rename_seed': 8}: oracle answer and reward preserved
- PASS: h06_interacting {'permute_seed': 13}: oracle answer and reward preserved
- PASS: h06_interacting {'remap_seed': 17}: oracle answer and reward preserved
- PASS: h06_interacting {'rename_seed': 19}: oracle answer and reward preserved
- PASS: h13_mixed {'permute_seed': 13}: oracle answer and reward preserved
- PASS: h13_mixed {'remap_seed': 17}: oracle answer and reward preserved
- PASS: h13_mixed {'rename_seed': 19}: oracle answer and reward preserved

### 5. Engineering and explanation (10)

Run time: A_unit_tests 199.8 s

#### A_unit_tests (1/1)

- PASS: unittest: 670 run, 652 passed, 18 skipped

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.9351 | 0.9351 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 32.45 | 0.1507 | 1.0 | 0.9508 | 0.9299 | 0 | 0.0 |
| hidden_like | flag_all | 20 | -1.0 | -0.9974 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0015 | 3.0 | 0.1319 | 0.0 | -1.0 | -1.0 | 150 | 0.0 |
| hidden_like | oracle | 20 | 1.0 | 1.0 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| hidden_like | random | 20 | -0.715 | -0.715 | 0.0 | 0.0 | 0.0 | 0.0 | 0.15 | 0.15 | 26.55 | 0.1364 | 0.15 | 0.14 | -1.0 | 3 | 0.0 |
| hidden_like | recon | 20 | -0.6766 | -0.6766 | 0.1177 | 0.5258 | 0.1049 | 0.7321 | 0.1868 | 0.1868 | 32.45 | 0.1382 | 0.0 | -1.0 | -0.5688 | 83 | 0.0 |
| hidden_like | silent | 20 | -0.5 | -0.5 | 0.0 | 0.0 | n/a | 0.0 | 0.25 | 0.25 | 0.0 | 0.1288 | 0.25 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | amount=1, search=55 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | recon | duplicate_invoice=0.3333, unallocated_payment=1.0, wrong_fx_rate=0.7, wrong_period=0.8125 | not_flagged=15 |
| hidden_like | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0.9351 | 0.9351 | 0.0 | 1.0 | 1.0 |
| hidden_like | flag_all | -1.0 | -0.9974 | 0.0026 | 0.0 | 0.0015 |
| hidden_like | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| hidden_like | random | -0.715 | -0.715 | 0.0 | 0.15 | 0.15 |
| hidden_like | recon | -0.6766 | -0.6766 | 0.0 | 0.1868 | 0.1868 |
| hidden_like | silent | -0.5 | -0.5 | 0.0 | 0.25 | 0.25 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0 | - | 23.125 | 0 / 56 (0.0) | 0 / 249 |
| hidden_like | flag_all | 600 | boundary_doc=49, credit_receipt=51, legit_repeat=34, midnight_fx=22, multi_invoice_payment=7, near_issue=5, overpayment_refund=26, posting_lag=53, recurring=58, split_payment=38, unrelated=252, weekend_fx=5 | - | 0 / 56 (0.0) | 0 / 380 |
| hidden_like | oracle | 0 | - | - | - | 249 / 249 |
| hidden_like | random | 28 | boundary_doc=1, credit_receipt=1, legit_repeat=1, multi_invoice_payment=1, underpayment=1, unrelated=23 | - | 0 / 56 (0.0) | 0 / 90 |
| hidden_like | recon | 350 | boundary_doc=48, credit_receipt=135, legit_repeat=24, midnight_fx=28, multi_invoice_payment=1, near_issue=2, null_ref_receipt=1, overpayment_refund=48, posting_lag=10, recurring=7, split_payment=7, unrelated=39 | 23.125 | 15 / 56 (0.2679) | 0 / 2053 |
| hidden_like | silent | 0 | - | - | 0 / 56 (0.0) | 0 / 0 |

