// DuckDB running INSIDE the browser (WebAssembly), reading the public data files.
// There is no server or database online: every query runs on the visitor's device.
import * as duckdb from "@duckdb/duckdb-wasm";
import ehWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url";
import mvpWorker from "@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url";
import ehWasm from "@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url";
import mvpWasm from "@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url";

const BUNDLES: duckdb.DuckDBBundles = {
  mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
  eh: { mainModule: ehWasm, mainWorker: ehWorker },
};

// Public datasets written by `lupa export-public`, as gzipped CSV: DuckDB-WASM reads CSV
// (and gzip) with its core engine. Parquet would need an extension downloaded from
// extensions.duckdb.org at runtime, a third-party request our CSP forbids (ADR-0005).
// Codes are forced to text so "01" never becomes the number 1.
const TABLES: Record<string, Record<string, string>> = {
  processes: { ocid: "VARCHAR", month: "VARCHAR", buyer_id: "VARCHAR", cpc_division: "VARCHAR" },
  buyers: { buyer_id: "VARCHAR" },
  cpc_divisions: { cpc_division: "VARCHAR" },
  review_priority: { buyer_id: "VARCHAR" },
  r018_buyers: { buyer_id: "VARCHAR" },
  r003_buyers: { buyer_id: "VARCHAR" },
  lp01_flags: { buyer_id: "VARCHAR", cpc_division: "VARCHAR" },
  monthly_coverage: { source_month: "VARCHAR" },
};

let ready: Promise<duckdb.AsyncDuckDBConnection> | null = null;

function typesClause(types: Record<string, string>): string {
  return Object.entries(types)
    .map(([column, type]) => `'${column}': '${type}'`)
    .join(", ");
}

function connect(): Promise<duckdb.AsyncDuckDBConnection> {
  ready ??= (async () => {
    const bundle = await duckdb.selectBundle(BUNDLES);
    const worker = new Worker(bundle.mainWorker!);
    const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    const base = new URL("data/", document.baseURI).href;
    // Download all files at once. Some servers (Vite's preview, for one) add
    // "Content-Encoding: gzip" and the browser unzips the file on the way, others send
    // the raw .gz bytes, so we look at the first two bytes (1f 8b = gzip) to tell.
    const files = await Promise.all(
      Object.keys(TABLES).map(async (table) => {
        const response = await fetch(`${base}${table}.csv.gz`);
        // The dev server answers a missing file with the app's own index.html (status 200).
        const isPage = (response.headers.get("content-type") ?? "").includes("text/html");
        if (!response.ok || isPage) throw new Error(`Falta el archivo data/${table}.csv.gz`);
        const bytes = new Uint8Array(await response.arrayBuffer());
        const gzipped = bytes[0] === 0x1f && bytes[1] === 0x8b;
        return { table, bytes, name: gzipped ? `${table}.csv.gz` : `${table}.csv` };
      }),
    );
    const conn = await db.connect();
    // Table names and types are our own constants above, never user input.
    for (const { table, bytes, name } of files) {
      await db.registerFileBuffer(name, bytes);
      await conn.query(
        `create table ${table} as select * from read_csv('${name}', header = true, types = {${typesClause(TABLES[table]!)}})`,
      );
      await db.dropFile(name);
    }
    return conn;
  })();
  return ready;
}

/** Resolves when the data is loaded; rejects with the reason if it could not be. */
export async function whenReady(): Promise<void> {
  await connect();
}

export type Row = Record<string, unknown>;

/** Runs a query with ? placeholders. User input is ALWAYS passed as parameters, never
 *  pasted into the SQL text, so a search for `'; drop table x` is just text. */
export async function query(sql: string, params: unknown[] = []): Promise<Row[]> {
  const conn = await connect();
  const stmt = await conn.prepare(sql);
  try {
    const result = await stmt.query(...params);
    return result.toArray().map((r) => {
      const row: Row = {};
      for (const [k, v] of Object.entries(r.toJSON() as Row)) {
        row[k] = typeof v === "bigint" ? Number(v) : v;
      }
      return row;
    });
  } finally {
    await stmt.close();
  }
}
