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

## Pages

| Route | What it shows |
|---|---|
| `#/inicio` | Key figures, entities to review first (with plain-language reasons), processes per month |
| `#/contratos` | Search and filters over every process; `?q=`, `?provincia=`, `?entidad=` |
| `#/entidades` | Entity search; `#/entidades/<buyer_id>` is the entity profile |
| `#/mapa` | Provinces coloured by a chosen metric, with a ranked table |
| `#/preguntar` | Placeholder for Phase 7 (questions in Spanish) |

## Rules

- Signals are worded as reasons to look closer, never as accusations.
- Natural persons only appear as `Persona #xxxxxx` (ADR-0004); the export enforces it.
- Every value typed by a visitor goes to DuckDB as a query parameter.
- No requests to third parties: no CDNs, analytics or external fonts.

## Credits

- Province boundaries: [Natural Earth](https://www.naturalearthdata.com/) admin-1,
  public domain, simplified with mapshaper (`src/ecuadorProvinces.ts` is generated).
- Font: Public Sans, SIL Open Font License 1.1 (`src/assets/fonts/OFL.txt`).
