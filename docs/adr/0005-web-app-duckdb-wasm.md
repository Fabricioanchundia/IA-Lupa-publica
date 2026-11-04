# ADR-0005: Public website as a static app with DuckDB in the browser

- Status: accepted
- Date: 2026-11-04

## Context

Phase 6 needs a public website that people who are not engineers can use: search
contracts, open the profile of a public entity, compare provinces on a map and, in
Phase 7, ask questions in Spanish. It must be free to host, private by design, and
must not send visitors' data to third parties.

Options considered:

1. **Static pages generated in Python** (Jinja). Simple, but no search: every view has
   to be pre-rendered, and 340k contracts cannot be browsed that way.
2. **Evidence.dev.** It became a hosted product ("Evidence Studio") with login and its
   own hosting, which conflicts with free, self-hosted publishing.
3. **An API server + database.** Full flexibility, but it costs money to run and adds an
   attack surface (a public SQL endpoint).
4. **A static single-page app that runs DuckDB in the browser (DuckDB-WASM).** The
   public datasets are downloaded once; every search and filter runs on the
   visitor's device.

## Decision

Option 4: React + TypeScript + Vite in `web/`, with `@duckdb/duckdb-wasm`.

- `lupa export-public` writes the allowlisted public datasets to `web/public/data/`
  (privacy guard: ADR-0004).
- Files are **gzipped CSV**, not Parquet. DuckDB-WASM reads CSV and gzip with its core
  engine; Parquet needs an extension that it downloads from `extensions.duckdb.org` at
  runtime, a third-party request.
- The built site sets a strict Content-Security-Policy: only its own files
  (`'self'`), plus `'wasm-unsafe-eval'` so the browser may run WebAssembly. No CDNs,
  no analytics, no external fonts (Public Sans is bundled, OFL).
- User input is always passed to DuckDB as prepared-statement parameters, never
  concatenated into SQL.
- Province boundaries come from Natural Earth (public domain), simplified and
  pre-converted to SVG paths at development time, so no map library or tile server is
  needed.

## Consequences

- Hosting is free (GitHub Pages) and there is no server to attack or pay for.
- First visit downloads the DuckDB WebAssembly file (~8–9 MB compressed) plus the data;
  later visits use the browser cache. The site is slower to open on weak connections.
- All public data is downloadable by anyone, which is intended: only the allowlisted,
  privacy-checked columns are exported.
- The data files are build outputs and are not committed (`web/public/data/` is
  ignored). How they reach GitHub Pages is decided in the deployment step.
