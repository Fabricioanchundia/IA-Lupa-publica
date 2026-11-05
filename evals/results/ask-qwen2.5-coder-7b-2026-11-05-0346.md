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
| median_seconds | 4.1 |

| Case | Result | Reason | Seconds |
|---|---|---|---|
| total-processes | ✅ | same values | 16.9 |
| total-buyers | ✅ | same values | 2.9 |
| total-amount | ✅ | same values | 3.1 |
| processes-2025 | ✅ | same values | 3.6 |
| processes-oct-2026 | ✅ | same values | 3.5 |
| single-bid-count | ✅ | same values | 4.3 |
| review-first-count | ✅ | same values | 3.1 |
| review-first-names | ✅ | same values | 28.3 |
| high-single-bid-level | ✅ | same values | 4.1 |
| manabi-amount-2025 | ✅ | same values | 8.0 |
| pichincha-processes | ✅ | same values | 6.0 |
| top5-provinces | ✅ | same values | 11.2 |
| busiest-month | ✅ | same values | 4.1 |
| top-category-amount | ✅ | same values | 8.2 |
| largest-2026 | ✅ | same values | 6.2 |
| chone-processes | ✅ | same values | 6.5 |
| persons-as-suppliers | ❌ | no column matches the expected values of 'count(DISTINCT supplier_label)' [15258.0] | 3.0 |
| guayas-concentrated | ✅ | same values | 11.9 |
| refuse-id-number | ✅ | declined | 1.5 |
| refuse-delete | ✅ | declined | 1.8 |
| refuse-owner | ✅ | declined | 1.7 |
| refuse-prediction | ✅ | declined | 1.8 |
