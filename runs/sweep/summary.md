# Organizer sweep

`python tools/organizer_sweep.py OUT_DIR 60 --record`: the closed path (`check --seeds-file --secret-env`) over the stress mix and the boundary mix. The contract battery also ran in-process on every feasible episode (the check itself runs it on one episode per seeds file).

- code: code 1265d019a068c2df0c71a5ffdcb28dade250d4040ca084feb851dccbe26dbec0 (60 files), Python 3.11.4, Windows-10-10.0.19045-SP0
- configurations: 423 (418 feasible, 5 infeasible, 0 generation failures)
- contract battery in-process: 418 of 418 episodes pass
- feasible by group: random 299, extreme 17, boundary 102
- chunks of 60: 7; every exit code 0: yes

## Chunks

| chunk | episodes | exit code | summary |
|---|---|---|---|
| 0 | 60 | 0 | summary: C_data 62/62, C_reward 1444/1444 (1 skipped), D_paired 371/371, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1906 named checks of 66 kinds) |
| 1 | 60 | 0 | summary: C_data 62/62, C_reward 1428/1428, D_paired 373/373, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1891 named checks of 76 kinds) |
| 2 | 60 | 0 | summary: C_data 62/62, C_reward 1437/1437 (1 skipped), D_paired 371/371, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1899 named checks of 66 kinds) |
| 3 | 60 | 0 | summary: C_data 62/62, C_reward 1445/1445 (1 skipped), D_paired 371/371, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1907 named checks of 66 kinds) |
| 4 | 60 | 0 | summary: C_data 62/62, C_reward 1445/1445 (1 skipped), D_paired 371/371, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1907 named checks of 66 kinds) |
| 5 | 60 | 0 | summary: C_data 62/62, C_reward 1200/1200 (2 skipped), D_paired 373/373, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1665 named checks of 77 kinds) |
| 6 | 58 | 0 | summary: C_data 60/60, C_reward 1160/1160, D_paired 357/357 (4 skipped), E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1609 named checks of 77 kinds) |

## Generation failures (accepted by config.py, GenerationError in the generator)

- none

## Contract battery failures

- none

## Infeasible configurations (ConfigError, skipped)

- `random_271`: timezone UTC never has a UTC offset, but the requested errors need one
- `bnd_tz_UTC_utc_wall_clock`: timezone UTC never has a UTC offset, but the requested errors need one
- `bnd_counts_sales_invoices_max`: counts too large for the 100-step budget: 2014 prior, sales and purchase invoices need at least 122 pages to read in full, plus the submit; lower those counts
- `bnd_counts_purchase_invoices_max`: counts too large for the 100-step budget: 2020 prior, sales and purchase invoices need at least 122 pages to read in full, plus the submit; lower those counts
- `bnd_counts_prior_invoices_max`: counts too large for the 100-step budget: 2028 prior, sales and purchase invoices need at least 123 pages to read in full, plus the submit; lower those counts

## Boundary configurations that ran

- `bnd_foreign_none`
- `bnd_foreign_none_one_error_each_non_fx`
- `bnd_foreign_one`
- `bnd_foreign_three`
- `bnd_base_AED`
- `bnd_base_BHD`
- `bnd_base_CHF`
- `bnd_base_EUR`
- `bnd_base_GBP`
- `bnd_base_JPY`
- `bnd_base_KRW`
- `bnd_base_KWD`
- `bnd_base_KZT`
- `bnd_base_USD`
- `bnd_foreign_only_AED`
- `bnd_foreign_only_BHD`
- `bnd_foreign_only_CHF`
- `bnd_foreign_only_EUR`
- `bnd_foreign_only_GBP`
- `bnd_foreign_only_JPY`
- `bnd_foreign_only_KRW`
- `bnd_foreign_only_KWD`
- `bnd_foreign_only_KZT`
- `bnd_foreign_only_USD`
- `bnd_size_small`
- `bnd_size_medium`
- `bnd_size_large`
- `bnd_distractors_all_0`
- `bnd_distractors_all_8`
- `bnd_distractors_all_0_with_errors`
- `bnd_distractors_all_8_large`
- `bnd_distractor_legit_repeat_8`
- `bnd_distractor_recurring_8`
- `bnd_distractor_split_payment_8`
- `bnd_distractor_multi_invoice_payment_8`
- `bnd_distractor_underpayment_8`
- `bnd_distractor_overpayment_refund_8`
- `bnd_distractor_null_ref_receipt_8`
- `bnd_distractor_boundary_doc_8`
- `bnd_distractor_midnight_fx_8`
- `bnd_distractor_weekend_fx_8`
- `bnd_errors_all_0`
- `bnd_errors_max_total`
- `bnd_errors_duplicate_invoice_max`
- `bnd_errors_unallocated_payment_max`
- `bnd_errors_wrong_fx_rate_max`
- `bnd_errors_wrong_period_max`
- `bnd_interacting_boundary_fx_payment`
- `bnd_interacting_fx_invoice_partial_allocation`
- `bnd_interacting_both`
- `bnd_interacting_both_plus_max_errors`
- `bnd_twin`
- `bnd_twin_with_errors`
- `bnd_twin_off`
- `bnd_period_first_supported`
- `bnd_period_last_supported`
- `bnd_period_year_end`
- `bnd_period_leap_february`
- `bnd_period_century_february`
- `bnd_period_utc_wall_clock_dst_new_york`
- `bnd_period_dst_end_london`
- `bnd_period_dst_start_sydney`
- `bnd_period_boundary_fx_payment`
- `bnd_tz_Asia/Almaty_utc_wall_clock`
- `bnd_tz_Asia/Tokyo_utc_wall_clock`
- `bnd_tz_Asia/Kolkata_utc_wall_clock`
- `bnd_tz_Asia/Kathmandu_utc_wall_clock`
- `bnd_tz_Asia/Kuwait_utc_wall_clock`
- `bnd_tz_America/Sao_Paulo_utc_wall_clock`
- `bnd_tz_Europe/Berlin_utc_wall_clock`
- `bnd_tz_Europe/London_utc_wall_clock`
- `bnd_tz_America/New_York_utc_wall_clock`
- `bnd_tz_Australia/Sydney_utc_wall_clock`
- `bnd_tz_half_hour_offset_kolkata`
- `bnd_tz_quarter_hour_offset_kathmandu`
- `bnd_tz_negative_offset_sao_paulo`
- `bnd_rounding_half_even`
- `bnd_rounding_half_up`
- `bnd_id_style_prefixed`
- `bnd_id_style_slashed`
- `bnd_id_style_hex`
- `bnd_id_style_numeric`
- `bnd_ts_repr_local`
- `bnd_ts_repr_utc`
- `bnd_ts_repr_mixed`
- `bnd_row_order_time`
- `bnd_row_order_shuffled`
- `bnd_variant_duplicate_invoice_same_day_copy`
- `bnd_variant_unallocated_payment_missing`
- `bnd_variant_unallocated_payment_partial`
- `bnd_variant_wrong_fx_rate_utc_date`
- `bnd_variant_wrong_fx_rate_posting_date`
- `bnd_variant_wrong_fx_rate_stale_rate`
- `bnd_variant_wrong_fx_rate_transposed`
- `bnd_variant_wrong_period_booked_early`
- `bnd_variant_wrong_period_booked_late`
- `bnd_variant_wrong_period_utc_wall_clock`
- `bnd_counts_minimum`
- `bnd_counts_minimum_with_errors`
- `bnd_counts_customers_max`
- `bnd_counts_suppliers_max`
- `bnd_counts_target_rows_max`
