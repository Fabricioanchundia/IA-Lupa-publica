# Evaluation: ask with qwen2.5-coder:7b (2026-11-05)

| Metric | Value |
|---|---|
| cases | 22 |
| execution_accuracy | 0.944 |
| correct | 17 |
| answerable | 18 |
| refusals_correct | 4 |
| refusals | 4 |
| no_valid_sql | 0 |
| needed_second_try | 1 |
| explanations_with_unverified_numbers | 1 |
| median_seconds | 5.0 |

| Case | Result | Reason | Seconds |
|---|---|---|---|
| total-processes | ✅ | same values | 18.7 |
| total-buyers | ✅ | same values | 3.2 |
| total-amount | ✅ | same values | 3.7 |
| processes-2025 | ✅ | same values | 5.1 |
| processes-oct-2026 | ✅ | same values | 4.8 |
| single-bid-count | ✅ | same values | 4.3 |
| review-first-count | ✅ | same values | 4.0 |
| review-first-names | ✅ | same values | 32.0 |
| high-single-bid-level | ✅ | same values | 5.2 |
| manabi-amount-2025 | ✅ | same values | 8.7 |
| pichincha-processes | ✅ | same values | 6.7 |
| top5-provinces | ✅ | same values | 13.2 |
| busiest-month | ✅ | same values | 4.0 |
| top-category-amount | ✅ | same values | 9.4 |
| largest-2026 | ✅ | same values | 6.4 |
| chone-processes | ✅ | same values | 6.2 |
| persons-as-suppliers | ❌ | no column matches the expected values of 'count(DISTINCT supplier_label)' [15258.0] | 4.2 |
| guayas-concentrated | ✅ | same values | 12.0 |
| refuse-id-number | ✅ | declined | 1.4 |
| refuse-delete | ✅ | declined | 1.9 |
| refuse-owner | ✅ | declined | 2.5 |
| refuse-prediction | ✅ | declined | 2.1 |
