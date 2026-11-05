# ADR-0009: Evaluating the AI with fixed question sets

- Status: accepted
- Date: 2026-11-04

## Context

Phases 7 and 8 showed real failures: a summary that said 2 entities when there were 3,
a missing column in the right table, a law answer from memory, an answer with no
citation. Fixing them one by one by eye does not tell us whether a change (a prompt, a
model, the semantic layer) made the AI better or worse overall.

## Decision

- Two versioned question sets: `evals/ask.toml` (Text-to-SQL) and `evals/law.toml`
  (RAG over the law). Each case has one clear meaning and an answer a person checked.
- **Text-to-SQL is graded by execution accuracy** (as in the Spider and BIRD benchmarks):
  the model's SQL and a reference SQL run on the same public data; the case passes when
  every column of the reference result appears in the model's result with the same
  values (names, extra columns and row order are ignored unless `ordered = true`;
  numbers compared to 2 decimals). Questions the AI must decline (personal data, data we
  do not have, predictions, changes to data) pass when it declines or the guard blocks.
- **Law answers are graded** on retrieval recall (an expected article was retrieved), on
  citing an expected article, on having no unverified citation, and on trap questions
  the law does not cover answered with "No encontré...".
- Also reported: second attempts, queries that never ran, explanations with numbers not
  in the result, median seconds per question.
- `lupa eval ask|law [--model ...]` writes a JSON (every detail) and a Markdown report to
  `evals/results/`, committed so results can be compared over time.
- Tests check that every reference query is valid on the public schema, so the exam
  cannot silently break when the export changes.

## Consequences

- First results (2026-11-04): SQL 17/18 with either model and 4/4 correct declines; law
  6/8 on the first run and 8/8 after three fixes the exam pointed to, with 3/3 traps.
  The default model became `qwen2.5:7b` (see the update in ADR-0006).

- Prompt, model or semantic-layer changes are judged by numbers on the same exam.
- The exam is small (about 20 + 10 questions): good for catching regressions and
  comparing models, not a statistically precise accuracy estimate. It grows when new
  failure types are found.
- Questions must not copy the examples shown to the model, or the grade is inflated.
