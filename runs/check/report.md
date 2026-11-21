# auditgym check report

Result: **PASS** in 431 s, version 0.5.0.

Episodes: public master string auditgym-check-v1.

Policy isolation: the host's user (no uid switch on this machine).

Code: code 1196da171b668e0cacb80c786d67e501fd5961728e11a43607700d959da170c5 (60 files), Python 3.11.4, Windows-10-10.0.19045-SP0.

Coverage: 717 named checks of 84 kinds (a kind is one property; most run on every episode they apply to).

## Checks (grouped by rubric criterion)

### 1. Contract and isolation (25)

Run time: F_contract 0.0 s, E_leaks 0.4 s

#### F_contract (20/20)

- PASS: ep_f156a933fec1fa22: reset returns exactly task, manifest, policy and remaining_steps
- PASS: ep_f156a933fec1fa22: every later observation has only result, error and remaining_steps
- PASS: ep_f156a933fec1fa22: a page holds at most 50 rows and paging reaches every row once, in order (ledger)
- PASS: ep_f156a933fec1fa22: the cursor is stable: the same cursor returns the same page, also in a fresh environment
- PASS: ep_f156a933fec1fa22: a page limit above the maximum is refused with a bounded error
- PASS: ep_f156a933fec1fa22: an unknown ID gives a bounded error and spends a step
- PASS: ep_f156a933fec1fa22: an unknown action gives a bounded error and spends a step
- PASS: ep_f156a933fec1fa22: the calculator evaluates a valid expression
- PASS: ep_f156a933fec1fa22: the calculator rejects __import__('os')
- PASS: ep_f156a933fec1fa22: the calculator rejects 2**8
- PASS: ep_f156a933fec1fa22: the calculator rejects 1/0
- PASS: ep_f156a933fec1fa22: after submit the episode is finished and further steps change nothing
- PASS: ep_f156a933fec1fa22: at step 100 (not before) the episode truncates with an empty answer
- PASS: ep_f156a933fec1fa22: the time limit on a frozen clock truncates with an empty answer
- PASS: ep_f156a933fec1fa22: eval mode returns reward 0 on every step, including the last
- PASS: ep_f156a933fec1fa22: info carries only episode_id in eval mode, also at the end
- PASS: ep_f156a933fec1fa22: an invalid submission scores -1
- PASS: ep_f156a933fec1fa22: a foreign episode_id scores -1
- PASS: ep_f156a933fec1fa22: all 10 sampled observations validate against observation.schema.json
- PASS: ep_f156a933fec1fa22: seeded contract fuzz (300 actions, reset every episode end) has 0 invariant violations

#### E_leaks (3/3)

- PASS: 1997 observations contain only the allowed fields
- PASS: no answer-key markers in any observation
- PASS: oracle trajectories are never published

### 2. Data and answer key (25)

Run time: B_committed_episodes 6.6 s, C_data 4.8 s

#### B_committed_episodes (60/60)

- PASS: train/t01_clean_small regenerates byte-identically
- PASS: train/t01_clean_small regenerates from directory provenance
- PASS: train/t01_clean_small verifies (0 issues)
- PASS: train/t02_clean_distractors regenerates byte-identically
- PASS: train/t02_clean_distractors regenerates from directory provenance
- PASS: train/t02_clean_distractors verifies (0 issues)
- PASS: train/t03_duplicate regenerates byte-identically
- PASS: train/t03_duplicate regenerates from directory provenance
- PASS: train/t03_duplicate verifies (1 issues)
- PASS: train/t04_unallocated regenerates byte-identically
- PASS: train/t04_unallocated regenerates from directory provenance
- PASS: train/t04_unallocated verifies (1 issues)
- PASS: train/t05_fx_rate regenerates byte-identically
- PASS: train/t05_fx_rate regenerates from directory provenance
- PASS: train/t05_fx_rate verifies (1 issues)
- PASS: train/t06_period regenerates byte-identically
- PASS: train/t06_period regenerates from directory provenance
- PASS: train/t06_period verifies (1 issues)
- PASS: train/t07_boundary_fx_payment regenerates byte-identically
- PASS: train/t07_boundary_fx_payment regenerates from directory provenance
- PASS: train/t07_boundary_fx_payment verifies (2 issues)
- PASS: train/t08_fx_partial_allocation regenerates byte-identically
- PASS: train/t08_fx_partial_allocation regenerates from directory provenance
- PASS: train/t08_fx_partial_allocation verifies (2 issues)
- PASS: train/t09_boundary_utc_clock regenerates byte-identically
- PASS: train/t09_boundary_utc_clock regenerates from directory provenance
- PASS: train/t09_boundary_utc_clock verifies (2 issues)
- PASS: train/t10_duplicate_twin_legit regenerates byte-identically
- PASS: train/t10_duplicate_twin_legit regenerates from directory provenance
- PASS: train/t10_duplicate_twin_legit verifies (0 issues)
- PASS: dev/d01_clean_repeats_jpy regenerates byte-identically
- PASS: dev/d01_clean_repeats_jpy regenerates from directory provenance
- PASS: dev/d01_clean_repeats_jpy verifies (0 issues)
- PASS: dev/d02_clean_kwd_medium regenerates byte-identically
- PASS: dev/d02_clean_kwd_medium regenerates from directory provenance
- PASS: dev/d02_clean_kwd_medium verifies (0 issues)
- PASS: dev/d03_duplicates_gbp regenerates byte-identically
- PASS: dev/d03_duplicates_gbp regenerates from directory provenance
- PASS: dev/d03_duplicates_gbp verifies (2 issues)
- PASS: dev/d04_unallocated_missing_eur regenerates byte-identically
- PASS: dev/d04_unallocated_missing_eur regenerates from directory provenance
- PASS: dev/d04_unallocated_missing_eur verifies (2 issues)
- PASS: dev/d05_fx_utc_stale_mixed_ts regenerates byte-identically
- PASS: dev/d05_fx_utc_stale_mixed_ts regenerates from directory provenance
- PASS: dev/d05_fx_utc_stale_mixed_ts verifies (2 issues)
- PASS: dev/d06_period_dst_march regenerates byte-identically
- PASS: dev/d06_period_dst_march regenerates from directory provenance
- PASS: dev/d06_period_dst_march verifies (2 issues)
- PASS: dev/d07_boundary_negative_offset regenerates byte-identically
- PASS: dev/d07_boundary_negative_offset regenerates from directory provenance
- PASS: dev/d07_boundary_negative_offset verifies (3 issues)
- PASS: dev/d08_both_interacting_kzt regenerates byte-identically
- PASS: dev/d08_both_interacting_kzt regenerates from directory provenance
- PASS: dev/d08_both_interacting_kzt verifies (5 issues)
- PASS: dev/d09_large_mixed regenerates byte-identically
- PASS: dev/d09_large_mixed regenerates from directory provenance
- PASS: dev/d09_large_mixed verifies (4 issues)
- PASS: dev/d10_large_dense_quarter_hour regenerates byte-identically
- PASS: dev/d10_large_dense_quarter_hour regenerates from directory provenance
- PASS: dev/d10_large_dense_quarter_hour verifies (10 issues)

#### C_data (22/22)

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
- PASS: sampling resamples (SampleRetry, BooksError or a sampling check) stay rare (0 over 20 episodes)
- PASS: no candidate episode was rejected by a correctness check (0 resampled)

### 3. Reward reliability (25)

Run time: C_reward 35.4 s

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
- PASS: ep_58ce7ad190f151ea: silence beats a false accusation on a clean ledger
- PASS: ep_58ce7ad190f151ea: 3 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 5 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 1 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 2 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 2 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: 13 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_58ce7ad190f151ea: saving steps separates equal answers only slightly
- PASS: ep_0c752ec235474543: silence beats a false accusation on a clean ledger
- PASS: ep_0c752ec235474543: 5 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 6 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 2 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 5 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 3 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: 32 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_0c752ec235474543: saving steps separates equal answers only slightly
- PASS: ep_003aeae3f9e8b04b: silence beats a false accusation on a clean ledger
- PASS: ep_003aeae3f9e8b04b: 3 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 3 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 6 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 2 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 3 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 2 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 8 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 3 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 4 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 3 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: 33 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_003aeae3f9e8b04b: saving steps separates equal answers only slightly
- PASS: ep_3d5aaec0030a88b0: silence beats a false accusation on a clean ledger
- PASS: ep_3d5aaec0030a88b0: 4 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 1 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 3 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 1 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 2 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 7 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 7 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 2 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 1 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: 17 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_3d5aaec0030a88b0: saving steps separates equal answers only slightly
- PASS: ep_89428ed7c789168c: silence beats a false accusation on a clean ledger
- PASS: ep_89428ed7c789168c: 5 legit_repeat accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 2 recurring accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 5 split_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 1 multi_invoice_payment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 2 underpayment accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 3 overpayment_refund accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 3 null_ref_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 6 boundary_doc accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 4 credit_receipt accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 3 midnight_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 2 weekend_fx accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: 24 posting_lag accusation(s) each score -1, below silence, and satisfy no key but their own
- PASS: ep_89428ed7c789168c: saving steps separates equal answers only slightly
- PASS: ep_f156a933fec1fa22: correct answer with evidence beats silence
- PASS: ep_f156a933fec1fa22: repeating findings gains nothing
- PASS: ep_f156a933fec1fa22: guessed ids is not a true positive
- PASS: ep_f156a933fec1fa22: unsupported evidence is not a true positive
- PASS: ep_f156a933fec1fa22: wrong currency is not a true positive
- PASS: ep_f156a933fec1fa22: amount off by 3 tolerances is not a true positive
- PASS: ep_f156a933fec1fa22: wrong type is not a true positive
- PASS: ep_f156a933fec1fa22: citing documents by alias keeps full credit
- PASS: ep_f156a933fec1fa22: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_f156a933fec1fa22: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_f156a933fec1fa22: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_f156a933fec1fa22: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_f156a933fec1fa22: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_f156a933fec1fa22: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 6 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: 22 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_f156a933fec1fa22: saving steps separates equal answers only slightly
- PASS: ep_dcb94f023bde271e: correct answer with evidence beats silence
- PASS: ep_dcb94f023bde271e: repeating findings gains nothing
- PASS: ep_dcb94f023bde271e: guessed ids is not a true positive
- PASS: ep_dcb94f023bde271e: unsupported evidence is not a true positive
- PASS: ep_dcb94f023bde271e: wrong currency is not a true positive
- PASS: ep_dcb94f023bde271e: amount off by 3 tolerances is not a true positive
- PASS: ep_dcb94f023bde271e: wrong type is not a true positive
- PASS: ep_dcb94f023bde271e: citing documents by alias keeps full credit
- PASS: ep_dcb94f023bde271e: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_dcb94f023bde271e: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_dcb94f023bde271e: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_dcb94f023bde271e: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_dcb94f023bde271e: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_dcb94f023bde271e: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: 27 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_dcb94f023bde271e: saving steps separates equal answers only slightly
- PASS: ep_6304ff618927cd3d: correct answer with evidence beats silence
- PASS: ep_6304ff618927cd3d: repeating findings gains nothing
- PASS: ep_6304ff618927cd3d: guessed ids is not a true positive
- PASS: ep_6304ff618927cd3d: unsupported evidence is not a true positive
- PASS: ep_6304ff618927cd3d: wrong currency is not a true positive
- PASS: ep_6304ff618927cd3d: amount off by 3 tolerances is not a true positive
- PASS: ep_6304ff618927cd3d: wrong type is not a true positive
- PASS: ep_6304ff618927cd3d: citing documents by alias keeps full credit
- PASS: ep_6304ff618927cd3d: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_6304ff618927cd3d: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_6304ff618927cd3d: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_6304ff618927cd3d: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_6304ff618927cd3d: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_6304ff618927cd3d: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 4 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 4 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 2 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: 15 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_6304ff618927cd3d: saving steps separates equal answers only slightly
- PASS: ep_c72528522204c2fc: correct answer with evidence beats silence
- PASS: ep_c72528522204c2fc: repeating findings gains nothing
- PASS: ep_c72528522204c2fc: guessed ids is not a true positive
- PASS: ep_c72528522204c2fc: unsupported evidence is not a true positive
- PASS: ep_c72528522204c2fc: wrong currency is not a true positive
- PASS: ep_c72528522204c2fc: amount off by 3 tolerances is not a true positive
- PASS: ep_c72528522204c2fc: wrong type is not a true positive
- PASS: ep_c72528522204c2fc: citing documents by alias keeps full credit
- PASS: ep_c72528522204c2fc: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_c72528522204c2fc: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_c72528522204c2fc: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_c72528522204c2fc: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_c72528522204c2fc: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_c72528522204c2fc: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 6 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 8 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: 24 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_c72528522204c2fc: saving steps separates equal answers only slightly
- PASS: ep_98ee61a952e55cea: correct answer with evidence beats silence
- PASS: ep_98ee61a952e55cea: repeating findings gains nothing
- PASS: ep_98ee61a952e55cea: guessed ids is not a true positive
- PASS: ep_98ee61a952e55cea: unsupported evidence is not a true positive
- PASS: ep_98ee61a952e55cea: wrong currency is not a true positive
- PASS: ep_98ee61a952e55cea: amount off by 3 tolerances is not a true positive
- PASS: ep_98ee61a952e55cea: wrong type is not a true positive
- PASS: ep_98ee61a952e55cea: citing documents by alias keeps full credit
- PASS: ep_98ee61a952e55cea: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_98ee61a952e55cea: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_98ee61a952e55cea: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_98ee61a952e55cea: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_98ee61a952e55cea: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_98ee61a952e55cea: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: 39 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_98ee61a952e55cea: saving steps separates equal answers only slightly
- PASS: ep_aec89364e7dffbac: correct answer with evidence beats silence
- PASS: ep_aec89364e7dffbac: repeating findings gains nothing
- PASS: ep_aec89364e7dffbac: guessed ids is not a true positive
- PASS: ep_aec89364e7dffbac: unsupported evidence is not a true positive
- PASS: ep_aec89364e7dffbac: wrong currency is not a true positive
- PASS: ep_aec89364e7dffbac: amount off by 3 tolerances is not a true positive
- PASS: ep_aec89364e7dffbac: wrong type is not a true positive
- PASS: ep_aec89364e7dffbac: citing documents by alias keeps full credit
- PASS: ep_aec89364e7dffbac: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_aec89364e7dffbac: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_aec89364e7dffbac: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_aec89364e7dffbac: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_aec89364e7dffbac: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_aec89364e7dffbac: 6 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 8 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: 33 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_aec89364e7dffbac: saving steps separates equal answers only slightly
- PASS: ep_ecdf3b26b4950984: correct answer with evidence beats silence
- PASS: ep_ecdf3b26b4950984: repeating findings gains nothing
- PASS: ep_ecdf3b26b4950984: guessed ids is not a true positive
- PASS: ep_ecdf3b26b4950984: unsupported evidence is not a true positive
- PASS: ep_ecdf3b26b4950984: wrong currency is not a true positive
- PASS: ep_ecdf3b26b4950984: amount off by 3 tolerances is not a true positive
- PASS: ep_ecdf3b26b4950984: wrong type is not a true positive
- PASS: ep_ecdf3b26b4950984: citing documents by alias keeps full credit
- PASS: ep_ecdf3b26b4950984: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_ecdf3b26b4950984: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_ecdf3b26b4950984: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_ecdf3b26b4950984: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_ecdf3b26b4950984: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_ecdf3b26b4950984: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 4 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 2 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: 35 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_ecdf3b26b4950984: saving steps separates equal answers only slightly
- PASS: ep_79def0f0d8b57cd0: correct answer with evidence beats silence
- PASS: ep_79def0f0d8b57cd0: repeating findings gains nothing
- PASS: ep_79def0f0d8b57cd0: guessed ids is not a true positive
- PASS: ep_79def0f0d8b57cd0: unsupported evidence is not a true positive
- PASS: ep_79def0f0d8b57cd0: wrong currency is not a true positive
- PASS: ep_79def0f0d8b57cd0: amount off by 3 tolerances is not a true positive
- PASS: ep_79def0f0d8b57cd0: wrong type is not a true positive
- PASS: ep_79def0f0d8b57cd0: citing documents by alias keeps full credit
- PASS: ep_79def0f0d8b57cd0: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_79def0f0d8b57cd0: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_79def0f0d8b57cd0: 24 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_79def0f0d8b57cd0: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_79def0f0d8b57cd0: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_79def0f0d8b57cd0: 1 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 2 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 3 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 2 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 2 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 1 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: 11 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_79def0f0d8b57cd0: saving steps separates equal answers only slightly
- PASS: ep_9abb871c873857db: correct answer with evidence beats silence
- PASS: ep_9abb871c873857db: repeating findings gains nothing
- PASS: ep_9abb871c873857db: guessed ids is not a true positive
- PASS: ep_9abb871c873857db: unsupported evidence is not a true positive
- PASS: ep_9abb871c873857db: wrong currency is not a true positive
- PASS: ep_9abb871c873857db: amount off by 3 tolerances is not a true positive
- PASS: ep_9abb871c873857db: wrong type is not a true positive
- PASS: ep_9abb871c873857db: citing documents by alias keeps full credit
- PASS: ep_9abb871c873857db: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_9abb871c873857db: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_9abb871c873857db: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_9abb871c873857db: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_9abb871c873857db: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_9abb871c873857db: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 2 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 1 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 2 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 3 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 2 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: 30 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_9abb871c873857db: saving steps separates equal answers only slightly
- PASS: ep_d1b9c92228a8b248: correct answer with evidence beats silence
- PASS: ep_d1b9c92228a8b248: repeating findings gains nothing
- PASS: ep_d1b9c92228a8b248: guessed ids is not a true positive
- PASS: ep_d1b9c92228a8b248: unsupported evidence is not a true positive
- PASS: ep_d1b9c92228a8b248: wrong currency is not a true positive
- PASS: ep_d1b9c92228a8b248: amount off by 3 tolerances is not a true positive
- PASS: ep_d1b9c92228a8b248: wrong type is not a true positive
- PASS: ep_d1b9c92228a8b248: citing documents by alias keeps full credit
- PASS: ep_d1b9c92228a8b248: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_d1b9c92228a8b248: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_d1b9c92228a8b248: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_d1b9c92228a8b248: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_d1b9c92228a8b248: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_d1b9c92228a8b248: 3 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 8 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: 42 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_d1b9c92228a8b248: saving steps separates equal answers only slightly
- PASS: ep_49d735850abe45d6: correct answer with evidence beats silence
- PASS: ep_49d735850abe45d6: repeating findings gains nothing
- PASS: ep_49d735850abe45d6: guessed ids is not a true positive
- PASS: ep_49d735850abe45d6: unsupported evidence is not a true positive
- PASS: ep_49d735850abe45d6: wrong currency is not a true positive
- PASS: ep_49d735850abe45d6: amount off by 3 tolerances is not a true positive
- PASS: ep_49d735850abe45d6: wrong type is not a true positive
- PASS: ep_49d735850abe45d6: citing documents by alias keeps full credit
- PASS: ep_49d735850abe45d6: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_49d735850abe45d6: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_49d735850abe45d6: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_49d735850abe45d6: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_49d735850abe45d6: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_49d735850abe45d6: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 4 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 6 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: 34 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_49d735850abe45d6: saving steps separates equal answers only slightly
- PASS: ep_e53025117dfa3bd5: correct answer with evidence beats silence
- PASS: ep_e53025117dfa3bd5: repeating findings gains nothing
- PASS: ep_e53025117dfa3bd5: guessed ids is not a true positive
- PASS: ep_e53025117dfa3bd5: unsupported evidence is not a true positive
- PASS: ep_e53025117dfa3bd5: wrong currency is not a true positive
- PASS: ep_e53025117dfa3bd5: amount off by 3 tolerances is not a true positive
- PASS: ep_e53025117dfa3bd5: wrong type is not a true positive
- PASS: ep_e53025117dfa3bd5: citing documents by alias keeps full credit
- PASS: ep_e53025117dfa3bd5: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_e53025117dfa3bd5: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_e53025117dfa3bd5: 28 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_e53025117dfa3bd5: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_e53025117dfa3bd5: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_e53025117dfa3bd5: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 7 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 2 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 7 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 11 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: 35 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e53025117dfa3bd5: saving steps separates equal answers only slightly
- PASS: ep_09d1c3dfd6e1d686: correct answer with evidence beats silence
- PASS: ep_09d1c3dfd6e1d686: repeating findings gains nothing
- PASS: ep_09d1c3dfd6e1d686: guessed ids is not a true positive
- PASS: ep_09d1c3dfd6e1d686: unsupported evidence is not a true positive
- PASS: ep_09d1c3dfd6e1d686: wrong currency is not a true positive
- PASS: ep_09d1c3dfd6e1d686: amount off by 3 tolerances is not a true positive
- PASS: ep_09d1c3dfd6e1d686: wrong type is not a true positive
- PASS: ep_09d1c3dfd6e1d686: citing documents by alias keeps full credit
- PASS: ep_09d1c3dfd6e1d686: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_09d1c3dfd6e1d686: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_09d1c3dfd6e1d686: 27 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_09d1c3dfd6e1d686: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_09d1c3dfd6e1d686: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_09d1c3dfd6e1d686: 4 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 4 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 9 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: 34 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_09d1c3dfd6e1d686: saving steps separates equal answers only slightly
- PASS: ep_240b409a62ce15e8: correct answer with evidence beats silence
- PASS: ep_240b409a62ce15e8: repeating findings gains nothing
- PASS: ep_240b409a62ce15e8: guessed ids is not a true positive
- PASS: ep_240b409a62ce15e8: unsupported evidence is not a true positive
- PASS: ep_240b409a62ce15e8: wrong currency is not a true positive
- PASS: ep_240b409a62ce15e8: amount off by 3 tolerances is not a true positive
- PASS: ep_240b409a62ce15e8: wrong type is not a true positive
- PASS: ep_240b409a62ce15e8: citing documents by alias keeps full credit
- PASS: ep_240b409a62ce15e8: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_240b409a62ce15e8: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_240b409a62ce15e8: 26 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_240b409a62ce15e8: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_240b409a62ce15e8: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_240b409a62ce15e8: 2 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 8 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 4 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 6 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 5 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 4 midnight_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: 37 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_240b409a62ce15e8: saving steps separates equal answers only slightly
- PASS: ep_e31498b826eac710: correct answer with evidence beats silence
- PASS: ep_e31498b826eac710: repeating findings gains nothing
- PASS: ep_e31498b826eac710: guessed ids is not a true positive
- PASS: ep_e31498b826eac710: unsupported evidence is not a true positive
- PASS: ep_e31498b826eac710: wrong currency is not a true positive
- PASS: ep_e31498b826eac710: amount off by 3 tolerances is not a true positive
- PASS: ep_e31498b826eac710: wrong type is not a true positive
- PASS: ep_e31498b826eac710: citing documents by alias keeps full credit
- PASS: ep_e31498b826eac710: type shotgun (copies under 3 other types) costs exactly 3 false positives
- PASS: ep_e31498b826eac710: amount ladder (4 neighbouring amounts) costs exactly 4 false positives
- PASS: ep_e31498b826eac710: 25 junk findings on top of the answer give exactly clip(2F1-1) and stay below the answer alone
- PASS: ep_e31498b826eac710: evidence padded to 10 IDs stays a true positive (published rule)
- PASS: ep_e31498b826eac710: right amount with the ID of an unrelated real invoice is not a true positive
- PASS: ep_e31498b826eac710: 5 legit_repeat accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 recurring accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 5 split_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 2 multi_invoice_payment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 underpayment accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 overpayment_refund accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 null_ref_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 5 boundary_doc accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 credit_receipt accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 3 weekend_fx accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: 31 posting_lag accusation(s) each cost exactly one false positive and match no answer-key issue
- PASS: ep_e31498b826eac710: saving steps separates equal answers only slightly

### 4. Reproducibility (15)

Run time: B_replay 1.6 s, D_paired 34.3 s

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

Run time: A_unit_tests 347.4 s

#### A_unit_tests (1/1)

- PASS: unittest: 619 run, 608 passed, 11 skipped

## Baselines on the 20 hidden-like episodes (eval mode, isolated agent process)

| split | policy | n | return | soft return | P | R | micro P | micro R | F1 | soft F1 | steps | agent s | closed | return clean | return errors | FP on clean | unobserved citations |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hidden_like | auditor | 20 | 0.9357 | 0.9357 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 32.15 | 0.0169 | 1.0 | 0.9492 | 0.9312 | 0 | 0.0 |
| hidden_like | flag_all | 20 | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 | 0.0024 | 0.0 | -1.0 | -1.0 | 150 | 0.0 |
| hidden_like | oracle | 20 | 1.0 | 1.0 | 0.75 | 0.75 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 | 1.0 | 0 | 1.0 |
| hidden_like | random | 20 | -0.9077 | -0.9077 | 0.0 | 0.0 | 0.0 | 0.0 | 0.05 | 0.05 | 22.55 | 0.0047 | 0.05 | -0.6308 | -1.0 | 7 | 0.0 |
| hidden_like | recon | 20 | -0.67 | -0.67 | 0.1202 | 0.515 | 0.1198 | 0.7143 | 0.1893 | 0.1893 | 32.15 | 0.0108 | 0.0 | -1.0 | -0.56 | 73 | 0.0 |
| hidden_like | silent | 20 | -0.5 | -0.5 | 0.0 | 0.0 | n/a | 0.0 | 0.25 | 0.25 | 0.0 | 0.0002 | 0.25 | 1.0 | -1.0 | 0 | n/a |

P and R are macro means over episodes. A clean episode has no TP, so even a correct empty answer scores P = R = 0 there; this is why macro P/R can be below 1 (the oracle's is, on sets with clean episodes). micro P = sum TP / sum (TP+FP) and micro R = sum TP / sum (TP+FN) pool all episodes and do not have this artefact. soft return is the experimental reward (see the reward table).

## Failure analysis

| split | policy | recall by type | miss reasons |
|---|---|---|---|
| hidden_like | auditor | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | flag_all | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | oracle | duplicate_invoice=1.0, unallocated_payment=1.0, wrong_fx_rate=1.0, wrong_period=1.0 | - |
| hidden_like | random | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |
| hidden_like | recon | duplicate_invoice=0.2222, unallocated_payment=1.0, wrong_fx_rate=0.75, wrong_period=0.75 | not_flagged=16 |
| hidden_like | silent | duplicate_invoice=0.0, unallocated_payment=0.0, wrong_fx_rate=0.0, wrong_period=0.0 | search=56 |

**Common vs experimental reward**

| split | policy | common return | experimental (soft) return | difference | F1 | soft F1 |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0.9357 | 0.9357 | 0.0 | 1.0 | 1.0 |
| hidden_like | flag_all | -1.0 | -1.0 | 0.0 | 0.0 | 0.0 |
| hidden_like | oracle | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |
| hidden_like | random | -0.9077 | -0.9077 | 0.0 | 0.05 | 0.05 |
| hidden_like | recon | -0.67 | -0.67 | 0.0 | 0.1893 | 0.1893 |
| hidden_like | silent | -0.5 | -0.5 | 0.0 | 0.25 | 0.25 |

**False positives, evidence timing, unobserved citations**

| split | policy | FP | FP causes | mean first full evidence step | issues seen, not flagged | unobserved citations (n / cited) |
|---|---|---|---|---|---|---|
| hidden_like | auditor | 0 | - | 24.0714 | 0 / 56 (0.0) | 0 / 249 |
| hidden_like | flag_all | 600 | boundary_doc=23, credit_receipt=75, legit_repeat=32, midnight_fx=5, multi_invoice_payment=8, overpayment_refund=59, posting_lag=54, recurring=77, split_payment=32, underpayment=4, unrelated=227, weekend_fx=4 | - | 0 / 56 (0.0) | 0 / 380 |
| hidden_like | oracle | 0 | - | - | - | 249 / 249 |
| hidden_like | random | 29 | boundary_doc=1, credit_receipt=4, legit_repeat=1, midnight_fx=1, near_issue=1, overpayment_refund=2, posting_lag=1, split_payment=2, unrelated=16 | - | 0 / 56 (0.0) | 0 / 95 |
| hidden_like | recon | 294 | boundary_doc=22, credit_receipt=108, legit_repeat=19, midnight_fx=30, multi_invoice_payment=2, near_issue=1, null_ref_receipt=1, overpayment_refund=60, posting_lag=7, recurring=5, split_payment=4, underpayment=2, unrelated=33 | 24.0714 | 16 / 56 (0.2857) | 0 / 1867 |
| hidden_like | silent | 0 | - | - | 0 / 56 (0.0) | 0 / 0 |

