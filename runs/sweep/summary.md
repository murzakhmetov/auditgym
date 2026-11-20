# Organizer sweep

`python tools/organizer_sweep.py OUT_DIR 60 --record`: the closed path (`check --seeds-file --secret-env`) over the stress mix and the boundary mix. The contract battery also ran in-process on every feasible episode (the check itself runs it on one episode per seeds file).

- configurations: 423 (401 feasible, 22 infeasible, 0 generation failures)
- contract battery in-process: 401 of 401 episodes pass
- feasible by group: random 282, extreme 17, boundary 102
- chunks of 60: 7; every exit code 0: yes

## Chunks

| chunk | episodes | exit code | summary |
|---|---|---|---|
| 0 | 60 | 0 | summary: C_data 62/62, C_reward 1444/1444 (1 skipped), D_paired 251/251, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1785 named checks of 70 kinds) |
| 1 | 60 | 0 | summary: C_data 62/62, C_reward 1428/1428, D_paired 253/253, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1771 named checks of 80 kinds) |
| 2 | 60 | 0 | summary: C_data 62/62, C_reward 1438/1438 (1 skipped), D_paired 251/251, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1779 named checks of 70 kinds) |
| 3 | 60 | 0 | summary: C_data 62/62, C_reward 1445/1445 (1 skipped), D_paired 251/251, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1786 named checks of 70 kinds) |
| 4 | 60 | 0 | summary: C_data 62/62, C_reward 1430/1430, D_paired 253/253, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1773 named checks of 78 kinds) |
| 5 | 60 | 0 | summary: C_data 62/62, C_reward 1159/1159 (2 skipped), D_paired 253/253, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1502 named checks of 82 kinds) |
| 6 | 41 | 0 | summary: C_data 43/43, C_reward 812/812, D_paired 177/177, E_leaks 3/3, F_contract 20/20, B_replay 5/5 (1060 named checks of 80 kinds) |

## Generation failures (accepted by config.py, GenerationError in the generator)

- none

## Contract battery failures

- none

## Infeasible configurations (ConfigError, skipped)

- `random_018`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-01 fails that. Nearest feasible periods: 2024-12, 2025-03
- `random_037`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2026-02 fails that. Nearest feasible periods: 2026-03, 2025-12
- `random_038`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2026-01 fails that. Nearest feasible periods: 2025-12, 2026-03
- `random_079`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-08 fails that. Nearest feasible periods: 2025-07, 2025-09
- `random_085`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-08 fails that. Nearest feasible periods: 2025-07, 2025-09
- `random_119`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2026-10 fails that. Nearest feasible periods: 2026-09, 2026-11
- `random_122`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-08 fails that. Nearest feasible periods: 2025-07, 2025-09
- `random_134`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-01 fails that. Nearest feasible periods: 2024-12, 2025-03
- `random_137`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2027-01 fails that. Nearest feasible periods: 2026-12, 2026-11
- `random_145`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-02 fails that. Nearest feasible periods: 2025-03, 2024-12
- `random_168`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2027-12 fails that. Nearest feasible periods: 2027-11, 2028-01
- `random_206`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2026-10 fails that. Nearest feasible periods: 2026-09, 2026-11
- `random_207`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2027-01 fails that. Nearest feasible periods: 2026-12, 2026-11
- `random_221`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-02 fails that. Nearest feasible periods: 2025-03, 2024-12
- `random_237`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2027-04 fails that. Nearest feasible periods: 2027-03, 2027-05
- `random_239`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-05 fails that. Nearest feasible periods: 2025-04, 2025-06
- `random_257`: boundary_fx_payment needs the last day of the period and the first day after it to be weekdays; period 2025-02 fails that. Nearest feasible periods: 2025-03, 2024-12
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
