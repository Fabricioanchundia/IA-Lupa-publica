# ADR-0007: An MCP server over the public data

- Status: accepted
- Date: 2026-11-04

## Context

Journalists, researchers and developers increasingly work through AI assistants (Claude
Desktop, IDE agents). The Model Context Protocol (MCP) is the open standard that lets an
assistant call external tools. Giving assistants direct, safe access to Lupa Pública lets
them answer with real numbers instead of guessing.

## Decision

- `lupa mcp` runs an MCP server (official Python SDK, `mcp` 2.x `MCPServer`) over
  **stdio**, on the user's own computer. Nothing is exposed to the internet.
- It loads **only the public datasets** into the same locked in-memory DuckDB used by
  `lupa ask` (ADR-0006).
- Four **read-only** tools, all annotated `readOnlyHint`:
  `describe_data` (semantic layer), `query_public_data` (the assistant's own SQL, checked
  by `sql_guard`, max 200 rows, SQL echoed back), `search_contracts` and `entity_profile`
  (fixed, parameterized SQL).
- Server instructions repeat the project rules: signals are not accusations, never try
  to identify `Persona #` suppliers.
- Results are Markdown tables, which assistants read reliably.

## Consequences

- Any MCP client can use Lupa Pública with no API key and no cost on our side; the
  assistant's own provider may send the (public) results to its cloud.
- The same two locks protect against prompt injection that tries to read files or write.
- New dependency: `mcp` (pinned to major version 2).
