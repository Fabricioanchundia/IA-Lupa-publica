# Lupa Pública — web app

Static React app. DuckDB runs **inside the browser** (WebAssembly) and queries the
public datasets exported by the Python pipeline. There is no backend. See
[ADR-0005](../docs/adr/0005-web-app-duckdb-wasm.md).

## Run it locally

```bash
# 1. From the repository root: export the public datasets into web/public/data/
uv run lupa export-public

# 2. Install and start the app (Node 22)
cd web
npm ci
npm run dev        # http://localhost:5173
```

`npm run build` type-checks and writes the site to `web/dist/`; `npm run preview`
serves that build (with the Content-Security-Policy that the dev server leaves out).

## Publish on GitHub Pages (free for public repositories)

The data files are not committed (they are build outputs, ~8 MB). They travel as a
GitHub Release instead:

```bash
set -a && source .env && set +a      # pseudonym key, needed by the export
uv run lupa export-public             # privacy-checked public datasets
scripts/publish_data.sh               # release "data-YYYY-MM-DD", then starts the pages workflow
gh run watch
```

The `pages` workflow downloads the newest `data-*` release, builds the app and deploys it.
One-time setup: Settings → Pages → Source: **GitHub Actions**.

## Pages

| Route | What it shows |
|---|---|
| `#/inicio` | Key figures, entities to review first (with plain-language reasons), processes per month |
| `#/contratos` | Search and filters over every process; `?q=`, `?provincia=`, `?entidad=` |
| `#/entidades` | Entity search; `#/entidades/<buyer_id>` is the entity profile |
| `#/mapa` | Provinces coloured by a chosen metric, with a ranked table |
| `#/preguntar` | AI gallery: reviewed questions answered by the local model, with SQL and a live re-run |
| `#/acerca` | About, data source, privacy, and how to ask for a correction (right of reply) |

## AI gallery (Phase 7, free)

A hosted model would cost money for every visitor, so the questions in
`web/ask-examples.txt` are answered on the developer's computer with Ollama and saved to
`web/src/askExamples.json` (privacy-checked). Review every answer before committing:

```bash
uv run lupa ask-examples          # needs Ollama running and web/public/data exported
```

Visitors can re-run each example's SQL in their own browser with "Comprobar en vivo".

## Rules

- Signals are worded as reasons to look closer, never as accusations.
- Natural persons only appear as `Persona #xxxxxx` (ADR-0004); the export enforces it.
- Every value typed by a visitor goes to DuckDB as a query parameter.
- No requests to third parties: no CDNs, analytics or external fonts.

## Credits

- Province boundaries: [Natural Earth](https://www.naturalearthdata.com/) admin-1,
  public domain, simplified with mapshaper (`src/ecuadorProvinces.ts` is generated).
- Font: Public Sans, SIL Open Font License 1.1 (`src/assets/fonts/OFL.txt`).
