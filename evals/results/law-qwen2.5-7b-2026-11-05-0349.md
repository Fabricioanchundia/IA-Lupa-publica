# Evaluation: law with qwen2.5:7b (2026-11-05)

| Metric | Value |
|---|---|
| cases | 11 |
| correct | 7 |
| answerable | 8 |
| accuracy | 0.875 |
| retrieval_recall | 1.0 |
| cited_expected | 0.875 |
| answers_with_unverified_citations | 1 |
| traps_correct | 3 |
| traps | 3 |
| median_seconds | 13.5 |

| Case | Result | Reason | Seconds |
|---|---|---|---|
| infima-cuantia | ✅ | cited the expected article | 27.6 |
| infima-procedure | ✅ | cited the expected article | 18.7 |
| subasta-inversa | ✅ | cited the expected article | 10.0 |
| subasta-reglas | ❌ | unverified citations ['[RGLOSNCP Art. 258,1]', '[RGLOSNCP Art. 258,2]', '[RGLOSNCP Art. 258,3]', '[RGLOSNCP Art. 258,4]', '[RGLOSNCP Art. 258,5]', '[RGLOSNCP Art. 258,6]'] | 30.8 |
| subasta-corporativa | ✅ | cited the expected article | 13.8 |
| objeto-ley | ✅ | cited the expected article | 10.5 |
| obligaciones-proveedores | ✅ | cited the expected article | 17.4 |
| retencion-pagos | ✅ | cited the expected article | 13.5 |
| trap-robbery | ✅ | said it did not find it | 7.6 |
| trap-salary | ✅ | said it did not find it | 5.8 |
| trap-geography | ✅ | said it did not find it | 7.5 |
