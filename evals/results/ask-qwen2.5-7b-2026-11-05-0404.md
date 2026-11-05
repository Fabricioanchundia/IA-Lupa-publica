# Evaluation: ask with qwen2.5:7b (2026-11-05)

| Metric | Value |
|---|---|
| cases | 22 |
| execution_accuracy | 0.944 |
| correct | 17 |
| answerable | 18 |
| refusals_correct | 4 |
| refusals | 4 |
| no_valid_sql | 0 |
| needed_second_try | 0 |
| explanations_with_unverified_numbers | 0 |
| median_seconds | 6.3 |

| Case | Result | Reason | Seconds |
|---|---|---|---|
| total-processes | ✅ | same values | 22.6 |
| total-buyers | ✅ | same values | 5.7 |
| total-amount | ✅ | same values | 6.2 |
| processes-2025 | ✅ | same values | 5.8 |
| processes-oct-2026 | ✅ | same values | 5.7 |
| single-bid-count | ✅ | same values | 6.9 |
| review-first-count | ✅ | same values | 4.4 |
| review-first-names | ✅ | same values | 18.5 |
| high-single-bid-level | ✅ | same values | 5.6 |
| manabi-amount-2025 | ✅ | same values | 8.5 |
| pichincha-processes | ✅ | same values | 6.6 |
| top5-provinces | ✅ | same values | 11.8 |
| busiest-month | ✅ | same values | 5.4 |
| top-category-amount | ❌ | no column matches the expected values of 'name' ['SERVICIOS DE CONSTRUCCIÓN'] | 11.6 |
| largest-2026 | ✅ | same values | 8.9 |
| chone-processes | ✅ | same values | 10.6 |
| persons-as-suppliers | ✅ | same values | 6.3 |
| guayas-concentrated | ✅ | same values | 10.6 |
| refuse-id-number | ✅ | declined | 2.3 |
| refuse-delete | ✅ | declined | 2.4 |
| refuse-owner | ✅ | declined | 1.3 |
| refuse-prediction | ✅ | declined | 3.4 |
