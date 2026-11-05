# Evaluation: law with qwen2.5:7b (2026-11-05)

| Metric | Value |
|---|---|
| cases | 11 |
| correct | 6 |
| answerable | 8 |
| accuracy | 0.75 |
| retrieval_recall | 1.0 |
| cited_expected | 0.75 |
| answers_with_unverified_citations | 1 |
| traps_correct | 3 |
| traps | 3 |
| median_seconds | 11.5 |

| Case | Result | Reason | Seconds |
|---|---|---|---|
| infima-cuantia | ✅ | cited the expected article | 23.8 |
| infima-procedure | ✅ | cited the expected article | 14.0 |
| subasta-inversa | ✅ | cited the expected article | 13.9 |
| subasta-reglas | ✅ | cited the expected article | 25.8 |
| subasta-corporativa | ❌ | unverified citations ['[LOSNCP Art. 123]'] | 11.5 |
| objeto-ley | ✅ | cited the expected article | 8.5 |
| obligaciones-proveedores | ❌ | did not cite ['LOSNCP 45'] | 14.5 |
| retencion-pagos | ✅ | cited the expected article | 11.1 |
| trap-robbery | ✅ | said it did not find it | 8.5 |
| trap-salary | ✅ | said it did not find it | 10.7 |
| trap-geography | ✅ | said it did not find it | 10.0 |
