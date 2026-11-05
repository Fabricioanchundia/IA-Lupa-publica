# ADR-0006: Questions in Spanish with Text-to-SQL and a local model

- Status: accepted
- Date: 2026-11-04

## Context

Phase 7 lets people ask questions in plain Spanish ("¿Qué hospital de Manabí gastó más
en medicamentos?") instead of using filters. A language model can write the SQL, but
models make mistakes and can be manipulated by what users type, and Lupa Pública must
never publish personal data or invent numbers.

## Decision

1. **Text-to-SQL, not "ask the model the answer".** The model only translates the
   question into SQL. The numbers come from running that SQL on the data, and the SQL is
   shown with every answer so anyone can check it.
2. **Public data only.** Queries run on an in-memory DuckDB loaded with the datasets of
   `lupa export-public` (ADR-0004 and ADR-0005 already apply to them). The model never
   sees the private database or the pseudonym key.
3. **Two locks.**
   - `sql_guard` parses the SQL with sqlglot (it never runs it) and accepts a single
     SELECT over the allowlisted tables only: no DDL/DML, no `ATTACH`/`COPY`/`PRAGMA`,
     no table functions, no file or settings functions, and a row limit.
   - The database is locked after loading: `enable_external_access = false`,
     extension auto-loading off, `lock_configuration = true`, memory and thread limits,
     and a time limit per query. A query that slipped past the first lock still could
     not read a file or change a setting.
4. **Self-correction, once.** If a query is refused or fails, the model sees the error
   and gets one more attempt; then we give up and say so.
5. **A semantic layer.** `semantic.py` explains every public table and column, plus a
   few real values (provinces, common procedures, date range) and four worked examples.
   A test fails if the export adds a column that is not explained.
6. **Local model first.** Development uses Ollama on the developer's computer: free,
   private, no API key. The default model is `qwen2.5-coder:7b` (`LUPA_LLM_MODEL`
   changes it). The `LanguageModel` protocol lets a hosted API be added later; that
   would cost money and needs a small backend to keep the key secret, so it is a
   separate decision.
7. **Neutral explanations.** A second call explains the result in simple Spanish using
   only the returned numbers, with the same rule as the website: signals are reasons to
   look closer, not accusations. The explanation is labeled as AI-written and a check
   marks any number in it that does not appear in the result (it cannot catch every
   slip, e.g. a wrong count that happens to equal another value; Phase 9 measures it).

## Consequences

- `lupa ask "..."` works offline once the model is downloaded; quality depends on the
  model and the semantic layer, and Phase 9 will measure it with a question set.
- The website keeps its "Preguntar con IA" page as a preview until we decide how to
  serve a model publicly (cost, abuse limits).
- New dependency: sqlglot (pure Python SQL parser).
