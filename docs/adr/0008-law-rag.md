# ADR-0008: Answers about procurement law with retrieval (RAG)

- Status: accepted
- Date: 2026-11-04

## Context

Many questions about public procurement are about the rules, not the data: "¿Cuál es el
plazo mínimo para ofertar en una subasta inversa?". Language models answer these from
memory, and memory of Ecuadorian law is incomplete, outdated (the LOSNCP was reformed in
2025) and sometimes invented. A wrong legal answer presented confidently is harmful.

## Decision

- **Retrieval-augmented generation over the official texts**: the LOSNCP and its General
  Regulation (RGLOSNCP), downloaded from the SERCOP portal and kept in `data/law/` (not in
  git).
- **Article = unit of retrieval.** `law.py` extracts the PDF text (pypdf), drops page
  numbers and running headers, and splits on article headings (`Art. 6.-`, `Artículo 6.-`,
  `Art. 45 bis.-`, `Art. (...).-`), requiring the dash so that references inside a
  sentence are not mistaken for headings. Long articles are split into parts of about
  1,500 characters with the same citation. `lupa law-index --check` reports gaps in the
  numbering to catch splitting errors before indexing.
- **Local multilingual embeddings** (Ollama `bge-m3`) stored in DuckDB
  (`data/law/law.duckdb`) and ranked with `list_cosine_similarity`; articles named in the
  question ("artículo 6") are always added. No vector database needed for ~1,000 chunks.
- **Grounded answers**: the model sees only the retrieved articles, must cite them as
  `[LOSNCP Art. N]`, and must say it did not find the answer otherwise. Every citation is
  checked against the retrieved set; unknown citations are flagged. Answers end with the
  articles consulted and "No es asesoría legal".
- **Answer model**: `qwen2.5:7b`, a general model (`LUPA_LAW_MODEL` changes it). On the
  same questions the coding model used for Text-to-SQL answered without citations, while
  the general model cited the article.
- **MCP**: when the index exists, `lupa mcp` adds a read-only `search_law` tool, so
  assistants can ground their own answers in the same articles.

## Consequences

- First real run: 121 LOSNCP articles and 441 RGLOSNCP articles, no gaps in numbering
  (headings came out at the end of the line in pypdf's plain mode; "layout" mode fixed it).
- An empty index once let the model answer from memory and invent a "Decreto Supremo";
  since then the model is never called without articles, and loose or missing citations
  are flagged.

- Answers are only as current as the PDFs: re-run `lupa law-index` after a reform.
- PDF extraction can break headings (two columns, hyphenation); the numbering report and
  tests on heading formats are the safety net.
- New dependency: pypdf.
