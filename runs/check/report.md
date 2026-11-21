# auditgym check report

Result: **PASS** in 390 s, version 0.3.0.

Episodes: public master string auditgym-check-v1.

Policy isolation: the host's user (no uid switch on this machine).

Code: code de70745efbcd5cab7af28a4a3b965ebc77b811fe96d82b1e9ce1c4abc765593f (60 files), Python 3.11.4, Windows-10-10.0.19045-SP0.

Coverage: 694 named checks of 83 kinds (a kind is one property; most run on every episode they apply to).

## Checks (grouped by rubric criterion)

### 1. Contract and isolation (25)

Run time: F_contract 0.0 s, E_leaks 0.4 s

#### F_contract (20/20)

- PASS: ep_dc5556b3932920fd: reset returns exactly task, manifest, policy and remaining_steps
- PASS: ep_dc5556b3932920fd: every later observation has only result, error and remaining_steps
- PASS: ep_dc5556b3932920fd: a page holds at most 50 rows and paging reaches every row once, in order (ledger)
- PASS: ep_dc5556b3932920fd: the cursor is stable: the same cursor returns the same page, also in a fresh environment
- PASS: ep_dc5556b3932920fd: a page limit above the maximum is refused with a bounded error
- PASS: ep_dc5556b3932920fd: an unknown ID gives a bounded error and spends a step
- PASS: ep_dc5556b3932920fd: an unknown action gives a bounded error and spends a step
- PASS: ep_dc5556b3932920fd: the calculator evaluates a valid expression
- PASS: ep_dc5556b3932920fd: the calculator rejects __import__('os')
- PASS: ep_dc5556b3932920fd: the calculator rejects 2**8
- PASS: ep_dc5556b3932920fd: the calculator rejects 1/0
- PASS: ep_dc5556b3932920fd: after submit the episode is finished and further steps change nothing
- PASS: ep_dc5556b3932920fd: at step 100 (not before) the episode truncates with an empty answer
- PASS: ep_dc5556b3932920fd: the time limit on a frozen clock truncates with an empty answer
- PASS: ep_dc5556b3932920fd: eval mode returns reward 0 on every step, including the last
- PASS: ep_dc5556b3932920fd: info carries only episode_id in eval mode, also at the end
- PASS: ep_dc5556b3932920fd: an invalid submission scores -1
- PASS: ep_dc5556b3932920fd: a foreign episode_id scores -1
- PASS: ep_dc5556b3932920fd: all 10 sampled observations validate against observation.schema.json
- PASS: ep_dc5556b3932920fd: seeded contract fuzz (300 actions, reset every episode end) has 0 invariant violations

#### E_leaks (3/3)

- PASS: 1920 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

### 2. Data and answer key (25)

Run time: B_committed_episodes 3.7 s, C_data 4.8 s

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
- PASS: h05_clean verifies (0 issues, 2 attempt(s))
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
- PASS: sampling resamples (SampleRetry, BooksError or a sampling check) stay rare (2 over 20 episodes)
- PASS: no candidate episode was rejected by a correctness check (2 resampled, all for sampling reasons)

### 3. Reward reliability (25)

Run time: C_reward 36.3 s

#### C_reward (465/465)

- PASS: oracle reaches reward 1.0 on all 20 episodes
- PASS: flag-everything attack scores poorly (mean return <= -0.9)
- PASS: scripted auditor closes every episode (no FP, no FN)
- PASS: ordering: oracle > auditor > recon > flag_all
- PASS: ordering on error episodes only: auditor > recon >= flag_all
- PASS: random explorer stays far below the auditor
- PASS: ordering: auditor > silent
- PASS: every run finishes inside 100 steps and 60 s
- PASS: no agent process failed
- PASS: ep_e71acf0f9722b264: silence beats a false accusation on a clean ledger
- PASS: ep_e71acf0f9722b264: 3 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 6 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 3 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: 19 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e71acf0f9722b264: saving steps separates equal answers only slightly
- PASS: ep_300bc86ce23d28f1: silence beats a false accusation on a clean ledger
- PASS: ep_300bc86ce23d28f1: 5 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 4 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 8 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 3 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: 36 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_300bc86ce23d28f1: saving steps separates equal answers only slightly
- PASS: ep_e6a7c68fd3135cea: silence beats a false accusation on a clean ledger
- PASS: ep_e6a7c68fd3135cea: 4 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 3 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 5 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 2 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 3 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 4 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 5 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 4 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 3 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: 29 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_e6a7c68fd3135cea: saving steps separates equal answers only slightly
- PASS: ep_f05a4b1598505207: silence beats a false accusation on a clean ledger
- PASS: ep_f05a4b1598505207: 4 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 4 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 2 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 1 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 2 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 7 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 2 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: 11 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_f05a4b1598505207: saving steps separates equal answers only slightly
- PASS: ep_cd697f0b3e81eecb: silence beats a false accusation on a clean ledger
- PASS: ep_cd697f0b3e81eecb: 3 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 7 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 2 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 7 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 8 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: 35 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_cd697f0b3e81eecb: saving steps separates equal answers only slightly
- PASS: ep_dc5556b3932920fd: correct answer with evidence beats silence
- PASS: ep_dc5556b3932920fd: repeating findings gains nothing
- PASS: ep_dc5556b3932920fd: guessed ids is not a true positive
- PASS: ep_dc5556b3932920fd: unsupported evidence is not a true positive
- PASS: ep_dc5556b3932920fd: wrong currency is not a true positive
- PASS: ep_dc5556b3932920fd: amount off by 3 tolerances is not a true positive
- PASS: ep_dc5556b3932920fd: wrong type is not a true positive
- PASS: ep_dc5556b3932920fd: citing documents by alias keeps full credit
- PASS: ep_dc5556b3932920fd: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_dc5556b3932920fd: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_dc5556b3932920fd: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_dc5556b3932920fd: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_dc5556b3932920fd: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_dc5556b3932920fd: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 4 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: 27 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dc5556b3932920fd: saving steps separates equal answers only slightly
- PASS: ep_8c6483dc3e4ed008: correct answer with evidence beats silence
- PASS: ep_8c6483dc3e4ed008: repeating findings gains nothing
- PASS: ep_8c6483dc3e4ed008: guessed ids is not a true positive
- PASS: ep_8c6483dc3e4ed008: unsupported evidence is not a true positive
- PASS: ep_8c6483dc3e4ed008: wrong currency is not a true positive
- PASS: ep_8c6483dc3e4ed008: amount off by 3 tolerances is not a true positive
- PASS: ep_8c6483dc3e4ed008: wrong type is not a true positive
- PASS: ep_8c6483dc3e4ed008: citing documents by alias keeps full credit
- PASS: ep_8c6483dc3e4ed008: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_8c6483dc3e4ed008: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_8c6483dc3e4ed008: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_8c6483dc3e4ed008: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_8c6483dc3e4ed008: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_8c6483dc3e4ed008: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: 37 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_8c6483dc3e4ed008: saving steps separates equal answers only slightly
- PASS: ep_46eab81f557cba5d: correct answer with evidence beats silence
- PASS: ep_46eab81f557cba5d: repeating findings gains nothing
- PASS: ep_46eab81f557cba5d: guessed ids is not a true positive
- PASS: ep_46eab81f557cba5d: unsupported evidence is not a true positive
- PASS: ep_46eab81f557cba5d: wrong currency is not a true positive
- PASS: ep_46eab81f557cba5d: amount off by 3 tolerances is not a true positive
- PASS: ep_46eab81f557cba5d: wrong type is not a true positive
- PASS: ep_46eab81f557cba5d: citing documents by alias keeps full credit
- PASS: ep_46eab81f557cba5d: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_46eab81f557cba5d: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_46eab81f557cba5d: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_46eab81f557cba5d: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_46eab81f557cba5d: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_46eab81f557cba5d: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 4 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 1 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 2 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: 10 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_46eab81f557cba5d: saving steps separates equal answers only slightly
- PASS: ep_452ad96041112bc7: correct answer with evidence beats silence
- PASS: ep_452ad96041112bc7: repeating findings gains nothing
- PASS: ep_452ad96041112bc7: guessed ids is not a true positive
- PASS: ep_452ad96041112bc7: unsupported evidence is not a true positive
- PASS: ep_452ad96041112bc7: wrong currency is not a true positive
- PASS: ep_452ad96041112bc7: amount off by 3 tolerances is not a true positive
- PASS: ep_452ad96041112bc7: wrong type is not a true positive
- PASS: ep_452ad96041112bc7: citing documents by alias keeps full credit
- PASS: ep_452ad96041112bc7: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_452ad96041112bc7: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_452ad96041112bc7: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_452ad96041112bc7: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_452ad96041112bc7: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_452ad96041112bc7: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: 29 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_452ad96041112bc7: saving steps separates equal answers only slightly
- PASS: ep_c5dfbaa2f9249949: correct answer with evidence beats silence
- PASS: ep_c5dfbaa2f9249949: repeating findings gains nothing
- PASS: ep_c5dfbaa2f9249949: guessed ids is not a true positive
- PASS: ep_c5dfbaa2f9249949: unsupported evidence is not a true positive
- PASS: ep_c5dfbaa2f9249949: wrong currency is not a true positive
- PASS: ep_c5dfbaa2f9249949: amount off by 3 tolerances is not a true positive
- PASS: ep_c5dfbaa2f9249949: wrong type is not a true positive
- PASS: ep_c5dfbaa2f9249949: citing documents by alias keeps full credit
- PASS: ep_c5dfbaa2f9249949: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_c5dfbaa2f9249949: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_c5dfbaa2f9249949: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_c5dfbaa2f9249949: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_c5dfbaa2f9249949: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_c5dfbaa2f9249949: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: 29 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c5dfbaa2f9249949: saving steps separates equal answers only slightly
- PASS: ep_69bece5a156e3b4c: correct answer with evidence beats silence
- PASS: ep_69bece5a156e3b4c: repeating findings gains nothing
- PASS: ep_69bece5a156e3b4c: guessed ids is not a true positive
- PASS: ep_69bece5a156e3b4c: unsupported evidence is not a true positive
- PASS: ep_69bece5a156e3b4c: wrong currency is not a true positive
- PASS: ep_69bece5a156e3b4c: amount off by 3 tolerances is not a true positive
- PASS: ep_69bece5a156e3b4c: wrong type is not a true positive
- PASS: ep_69bece5a156e3b4c: citing documents by alias keeps full credit
- PASS: ep_69bece5a156e3b4c: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_69bece5a156e3b4c: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_69bece5a156e3b4c: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_69bece5a156e3b4c: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_69bece5a156e3b4c: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_69bece5a156e3b4c: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 7 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: 46 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_69bece5a156e3b4c: saving steps separates equal answers only slightly
- PASS: ep_2f9b9966254f25f6: correct answer with evidence beats silence
- PASS: ep_2f9b9966254f25f6: repeating findings gains nothing
- PASS: ep_2f9b9966254f25f6: guessed ids is not a true positive
- PASS: ep_2f9b9966254f25f6: unsupported evidence is not a true positive
- PASS: ep_2f9b9966254f25f6: wrong currency is not a true positive
- PASS: ep_2f9b9966254f25f6: amount off by 3 tolerances is not a true positive
- PASS: ep_2f9b9966254f25f6: wrong type is not a true positive
- PASS: ep_2f9b9966254f25f6: citing documents by alias keeps full credit
- PASS: ep_2f9b9966254f25f6: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_2f9b9966254f25f6: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_2f9b9966254f25f6: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_2f9b9966254f25f6: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_2f9b9966254f25f6: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_2f9b9966254f25f6: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 3 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: 20 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_2f9b9966254f25f6: saving steps separates equal answers only slightly
- PASS: ep_14fdf811999d8e23: correct answer with evidence beats silence
- PASS: ep_14fdf811999d8e23: repeating findings gains nothing
- PASS: ep_14fdf811999d8e23: guessed ids is not a true positive
- PASS: ep_14fdf811999d8e23: unsupported evidence is not a true positive
- PASS: ep_14fdf811999d8e23: wrong currency is not a true positive
- PASS: ep_14fdf811999d8e23: amount off by 3 tolerances is not a true positive
- PASS: ep_14fdf811999d8e23: wrong type is not a true positive
- PASS: ep_14fdf811999d8e23: citing documents by alias keeps full credit
- PASS: ep_14fdf811999d8e23: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_14fdf811999d8e23: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_14fdf811999d8e23: 24 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_14fdf811999d8e23: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_14fdf811999d8e23: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_14fdf811999d8e23: 1 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: 9 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_14fdf811999d8e23: saving steps separates equal answers only slightly
- PASS: ep_68dd47e94aaf8a48: correct answer with evidence beats silence
- PASS: ep_68dd47e94aaf8a48: repeating findings gains nothing
- PASS: ep_68dd47e94aaf8a48: guessed ids is not a true positive
- PASS: ep_68dd47e94aaf8a48: unsupported evidence is not a true positive
- PASS: ep_68dd47e94aaf8a48: wrong currency is not a true positive
- PASS: ep_68dd47e94aaf8a48: amount off by 3 tolerances is not a true positive
- PASS: ep_68dd47e94aaf8a48: wrong type is not a true positive
- PASS: ep_68dd47e94aaf8a48: citing documents by alias keeps full credit
- PASS: ep_68dd47e94aaf8a48: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_68dd47e94aaf8a48: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_68dd47e94aaf8a48: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_68dd47e94aaf8a48: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_68dd47e94aaf8a48: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_68dd47e94aaf8a48: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: 31 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_68dd47e94aaf8a48: saving steps separates equal answers only slightly
- PASS: ep_6a90d70344927f55: correct answer with evidence beats silence
- PASS: ep_6a90d70344927f55: repeating findings gains nothing
- PASS: ep_6a90d70344927f55: guessed ids is not a true positive
- PASS: ep_6a90d70344927f55: unsupported evidence is not a true positive
- PASS: ep_6a90d70344927f55: wrong currency is not a true positive
- PASS: ep_6a90d70344927f55: amount off by 3 tolerances is not a true positive
- PASS: ep_6a90d70344927f55: wrong type is not a true positive
- PASS: ep_6a90d70344927f55: citing documents by alias keeps full credit
- PASS: ep_6a90d70344927f55: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_6a90d70344927f55: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_6a90d70344927f55: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_6a90d70344927f55: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_6a90d70344927f55: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_6a90d70344927f55: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 6 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 7 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: 31 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6a90d70344927f55: saving steps separates equal answers only slightly
- PASS: ep_954dd67e52464c07: correct answer with evidence beats silence
- PASS: ep_954dd67e52464c07: repeating findings gains nothing
- PASS: ep_954dd67e52464c07: guessed ids is not a true positive
- PASS: ep_954dd67e52464c07: unsupported evidence is not a true positive
- PASS: ep_954dd67e52464c07: wrong currency is not a true positive
- PASS: ep_954dd67e52464c07: amount off by 3 tolerances is not a true positive
- PASS: ep_954dd67e52464c07: wrong type is not a true positive
- PASS: ep_954dd67e52464c07: citing documents by alias keeps full credit
- PASS: ep_954dd67e52464c07: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_954dd67e52464c07: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_954dd67e52464c07: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_954dd67e52464c07: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_954dd67e52464c07: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_954dd67e52464c07: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 10 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: 44 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_954dd67e52464c07: saving steps separates equal answers only slightly
- PASS: ep_57c6a292b0392e44: correct answer with evidence beats silence
- PASS: ep_57c6a292b0392e44: repeating findings gains nothing
- PASS: ep_57c6a292b0392e44: guessed ids is not a true positive
- PASS: ep_57c6a292b0392e44: unsupported evidence is not a true positive
- PASS: ep_57c6a292b0392e44: wrong currency is not a true positive
- PASS: ep_57c6a292b0392e44: amount off by 3 tolerances is not a true positive
- PASS: ep_57c6a292b0392e44: wrong type is not a true positive
- PASS: ep_57c6a292b0392e44: citing documents by alias keeps full credit
- PASS: ep_57c6a292b0392e44: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_57c6a292b0392e44: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_57c6a292b0392e44: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_57c6a292b0392e44: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_57c6a292b0392e44: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_57c6a292b0392e44: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 9 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: 45 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_57c6a292b0392e44: saving steps separates equal answers only slightly
- PASS: ep_5047ed25c1976188: correct answer with evidence beats silence
- PASS: ep_5047ed25c1976188: repeating findings gains nothing
- PASS: ep_5047ed25c1976188: guessed ids is not a true positive
- PASS: ep_5047ed25c1976188: unsupported evidence is not a true positive
- PASS: ep_5047ed25c1976188: wrong currency is not a true positive
- PASS: ep_5047ed25c1976188: amount off by 3 tolerances is not a true positive
- PASS: ep_5047ed25c1976188: wrong type is not a true positive
- PASS: ep_5047ed25c1976188: citing documents by alias keeps full credit
- PASS: ep_5047ed25c1976188: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_5047ed25c1976188: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_5047ed25c1976188: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_5047ed25c1976188: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_5047ed25c1976188: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_5047ed25c1976188: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 10 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: 37 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_5047ed25c1976188: saving steps separates equal answers only slightly
- PASS: ep_f0c55f627fe79f76: correct answer with evidence beats silence
- PASS: ep_f0c55f627fe79f76: repeating findings gains nothing
- PASS: ep_f0c55f627fe79f76: guessed ids is not a true positive
- PASS: ep_f0c55f627fe79f76: unsupported evidence is not a true positive
- PASS: ep_f0c55f627fe79f76: wrong currency is not a true positive
- PASS: ep_f0c55f627fe79f76: amount off by 3 tolerances is not a true positive
- PASS: ep_f0c55f627fe79f76: wrong type is not a true positive
- PASS: ep_f0c55f627fe79f76: citing documents by alias keeps full credit
- PASS: ep_f0c55f627fe79f76: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_f0c55f627fe79f76: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_f0c55f627fe79f76: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_f0c55f627fe79f76: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_f0c55f627fe79f76: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_f0c55f627fe79f76: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 6 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 8 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: 44 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f0c55f627fe79f76: saving steps separates equal answers only slightly
- PASS: ep_6bea096f5619457c: correct answer with evidence beats silence
- PASS: ep_6bea096f5619457c: repeating findings gains nothing
- PASS: ep_6bea096f5619457c: guessed ids is not a true positive
- PASS: ep_6bea096f5619457c: unsupported evidence is not a true positive
- PASS: ep_6bea096f5619457c: wrong currency is not a true positive
- PASS: ep_6bea096f5619457c: amount off by 3 tolerances is not a true positive
- PASS: ep_6bea096f5619457c: wrong type is not a true positive
- PASS: ep_6bea096f5619457c: citing documents by alias keeps full credit
- PASS: ep_6bea096f5619457c: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_6bea096f5619457c: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_6bea096f5619457c: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_6bea096f5619457c: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_6bea096f5619457c: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_6bea096f5619457c: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: 45 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6bea096f5619457c: saving steps separates equal answers only slightly

### 4. Reproducibility (15)

Run time: B_replay 1.2 s, D_paired 33.1 s

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

Run time: A_unit_tests 311.0 s

#### A_unit_tests (1/1)

- PASS: unittest: 594 run, 583 passed, 11 skipped

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.9365 | 0.9365 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 31.75 | 0.0162 | 1.0 | 0.9528 | 0.9311 | 0 | 0.0 |
| hidden_like | flag_all | 20 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0026 | 0.0 | -1.0 | -1.0 | 150 | 0.0 |
| hidden_like | oracle | 20 | 1.0 | 1.0 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| hidden_like | random | 20 | -0.8042 | -0.8042 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 | 19.5 | 0.0033 | 0.1 | -0.2168 | -1.0 | 7 | 0.0 |
| hidden_like | recon | 20 | -0.6783 | -0.6783 | 0.119 | 0.47 | 0.1028 | 0.6607 | 0.1833 | 0.1833 | 31.75 | 0.0109 | 0.0 | -1.0 | -0.5711 | 78 | 0.0 |
| hidden_like | silent | 20 | -0.5 | -0.5 | 0.0 | 0.0 | n/a | 0.0 | 0.25 | 0.25 | 0.0 | 0.0002 | 0.25 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | recon | duplicate_invoice=0.0, unallocated_payment=1.0, wrong_fx_rate=0.75, wrong_period=0.6875 | not_flagged=19 |
| hidden_like | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0.9365 | 0.9365 | 0.0 | 1.0 | 1.0 |
| hidden_like | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| hidden_like | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| hidden_like | random | -0.8042 | -0.8042 | 0.0 | 0.1 | 0.1 |
| hidden_like | recon | -0.6783 | -0.6783 | 0.0 | 0.1833 | 0.1833 |
| hidden_like | silent | -0.5 | -0.5 | 0.0 | 0.25 | 0.25 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0 | - | 21.9107 | 0 / 56 (0.0) | 0 / 248 |
| hidden_like | flag_all | 600 | boundary_doc=20, credit_receipt=88, legit_repeat=15, midnight_fx=9, multi_invoice_payment=11, near_issue=6, overpayment_refund=36, posting_lag=44, recurring=91, split_payment=35, underpayment=7, unrelated=223, weekend_fx=15 | - | 0 / 56 (0.0) | 0 / 380 |
| hidden_like | oracle | 0 | - | - | - | 248 / 248 |
| hidden_like | random | 22 | credit_receipt=1, legit_repeat=2, overpayment_refund=1, posting_lag=1, split_payment=2, unrelated=15 | - | 0 / 56 (0.0) | 0 / 86 |
| hidden_like | recon | 323 | boundary_doc=32, credit_receipt=125, legit_repeat=23, midnight_fx=21, near_issue=1, overpayment_refund=60, posting_lag=9, recurring=5, split_payment=7, underpayment=1, unrelated=39 | 21.9107 | 19 / 56 (0.3393) | 0 / 1925 |
| hidden_like | silent | 0 | - | - | 0 / 56 (0.0) | 0 / 0 |

