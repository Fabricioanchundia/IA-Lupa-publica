import { useEffect, useMemo, useState } from "react";
import { query, type Row } from "../db";
import { fmtCompactMoney, fmtInt, fmtMoney, fmtMonth, provinceName, str, titleCase } from "../format";
import { href, type Route } from "../router";
import { PROCEDURE } from "../sql";

const PAGE_SIZE = 25;

type Filters = {
  text: string;
  province: string;
  year: string;
  procedure: string;
  category: string;
  buyer: string;
  signalsOnly: boolean;
};

const EMPTY: Filters = { text: "", province: "", year: "", procedure: "", category: "", buyer: "", signalsOnly: false };

// One row per process with the buyer's name/province and the category name joined in.
const FROM = `
  from processes as p
  left join buyers as b on p.buyer_id = b.buyer_id
  left join cpc_divisions as c on p.cpc_division = c.cpc_division`;

/** WHERE clause with ? placeholders + the values, in the same order. */
function where(f: Filters): [string, unknown[]] {
  const parts: string[] = [];
  const params: unknown[] = [];
  const text = f.text.trim();
  if (text) {
    parts.push("(p.title ilike ? or b.buyer_name ilike ? or p.supplier_label ilike ?)");
    params.push(`%${text}%`, `%${text}%`, `%${text}%`);
  }
  if (f.province) { parts.push("b.buyer_region = ?"); params.push(f.province); }
  if (f.year) { parts.push("left(p.month, 4) = ?"); params.push(f.year); }
  if (f.procedure) { parts.push(`${PROCEDURE()} = ?`); params.push(f.procedure); }
  if (f.category) { parts.push("p.cpc_division = ?"); params.push(f.category); }
  if (f.buyer) { parts.push("p.buyer_id = ?"); params.push(f.buyer); }
  if (f.signalsOnly) parts.push("(p.single_bid or p.short_period)");
  return [parts.length ? `where ${parts.join(" and ")}` : "", params];
}

function fromRoute(route: Route): Filters {
  const g = (k: string) => route.params.get(k) ?? "";
  return { ...EMPTY, text: g("q"), province: g("provincia"), buyer: g("entidad"), signalsOnly: g("senales") === "1" };
}

type Options = { provinces: string[]; years: string[]; procedures: string[]; categories: Row[] };

export default function Contracts({ route }: { route: Route }) {
  const initial = useMemo(() => fromRoute(route), [route]);
  const [filters, setFilters] = useState<Filters>(initial);
  const [draft, setDraft] = useState(initial.text);
  const [page, setPage] = useState(0);
  const [options, setOptions] = useState<Options>();
  const [buyerName, setBuyerName] = useState("");
  const [summary, setSummary] = useState<Row>();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      query("select distinct buyer_region as v from buyers where buyer_region is not null order by 1"),
      query("select distinct left(month, 4) as v from processes order by 1 desc"),
      query(`select ${PROCEDURE()} as v, count(*) as n from processes as p group by 1 order by 2 desc`),
      query(`select c.cpc_division, c.name, count(*) as n from processes as p
             join cpc_divisions as c on p.cpc_division = c.cpc_division group by 1, 2 order by 2`),
    ]).then(([p, y, t, c]) =>
      setOptions({
        provinces: p.map((r) => str(r.v)),
        years: y.map((r) => str(r.v)),
        procedures: t.map((r) => str(r.v)).filter(Boolean),
        categories: c,
      }),
    );
  }, []);

  useEffect(() => {
    if (!filters.buyer) return setBuyerName("");
    query("select buyer_name from buyers where buyer_id = ?", [filters.buyer]).then((r) =>
      setBuyerName(titleCase(r[0]?.buyer_name ?? filters.buyer)),
    );
  }, [filters.buyer]);

  // Debounce typing so we query once the user pauses.
  useEffect(() => {
    const id = setTimeout(() => {
      setFilters((f) => (f.text === draft ? f : { ...f, text: draft }));
      setPage(0);
    }, 250);
    return () => clearTimeout(id);
  }, [draft]);

  const [clause, params] = useMemo(() => where(filters), [filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      query(
        `select count(*) as n, sum(p.amount) as total,
                count(*) filter (where p.single_bid or p.short_period) as flagged ${FROM} ${clause}`,
        params,
      ),
      query(
        `select p.ocid, p.month, p.buyer_id, b.buyer_name, b.buyer_region, p.title, c.name as category,
                p.supplier_label, ${PROCEDURE()} as procedure, p.procedure as procedure_full, p.amount, p.tenderers, p.single_bid, p.short_period
         ${FROM} ${clause}
         order by p.month desc, p.amount desc nulls last limit ${PAGE_SIZE} offset ?`,
        [...params, page * PAGE_SIZE],
      ),
    ]).then(([s, r]) => {
      if (cancelled) return;
      setSummary(s[0]);
      setRows(r);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [clause, params, page]);

  const set = (patch: Partial<Filters>) => { setFilters((f) => ({ ...f, ...patch })); setPage(0); };
  const total = Number(summary?.n ?? 0);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const dirty = JSON.stringify(filters) !== JSON.stringify(EMPTY) || draft !== "";

  return (
    <section>
      <header className="page-head">
        <h1>Contratos</h1>
        <p>Busca entre los procesos de contratación publicados por el SERCOP.</p>
      </header>

      <div className="search">
        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Busca por descripción, entidad o proveedor: alcantarillado, medicamentos, Manta…"
          aria-label="Buscar contratos"
        />
      </div>

      <div className="filters">
        <label>Provincia
          <select value={filters.province} onChange={(e) => set({ province: e.target.value })}>
            <option value="">Todas</option>
            {options?.provinces.map((p) => <option key={p} value={p}>{provinceName(p)}</option>)}
          </select>
        </label>
        <label>Año
          <select value={filters.year} onChange={(e) => set({ year: e.target.value })}>
            <option value="">Todos</option>
            {options?.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label>Categoría
          <select value={filters.category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">Todas</option>
            {options?.categories.map((c) => (
              <option key={str(c.cpc_division)} value={str(c.cpc_division)}>{str(c.name)}</option>
            ))}
          </select>
        </label>
        <label>Procedimiento
          <select value={filters.procedure} onChange={(e) => set({ procedure: e.target.value })}>
            <option value="">Todos</option>
            {options?.procedures.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={filters.signalsOnly} onChange={(e) => set({ signalsOnly: e.target.checked })} />
          Solo con señales
        </label>
        {dirty && (
          <button type="button" className="link" onClick={() => { setFilters(EMPTY); setDraft(""); setPage(0); }}>
            Limpiar filtros
          </button>
        )}
      </div>

      {filters.buyer && (
        <p className="chip-row">
          <span className="chip">
            Entidad: {buyerName || "…"}
            <button type="button" aria-label="Quitar filtro de entidad" onClick={() => set({ buyer: "" })}>×</button>
          </span>
        </p>
      )}

      <div className="stats" aria-live="polite">
        <div><strong>{fmtInt(total)}</strong><span>contratos</span></div>
        <div><strong>{fmtCompactMoney(summary?.total)}</strong><span>monto total</span></div>
        <div><strong>{fmtInt(summary?.flagged)}</strong><span>con alguna señal</span></div>
      </div>

      <div className={`table-card${loading ? " is-loading" : ""}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">Mes</th>
              <th scope="col">Entidad</th>
              <th scope="col">Descripción</th>
              <th scope="col">Procedimiento</th>
              <th scope="col" className="num">Monto</th>
              <th scope="col">Señales</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={str(r.ocid)}>
                <td className="nowrap">{fmtMonth(r.month)}</td>
                <td>
                  <a href={href("entidades", str(r.buyer_id))}>{titleCase(r.buyer_name)}</a>
                  <small>{provinceName(r.buyer_region)}</small>
                </td>
                <td className="desc">
                  {str(r.title) || "Sin descripción"}
                  <small>
                    {[str(r.category), r.supplier_label ? `Proveedor: ${titleCase(r.supplier_label)}` : ""]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                  <small className="mono">{str(r.ocid)}</small>
                </td>
                <td title={str(r.procedure_full)}>{str(r.procedure) || "—"}</td>
                <td className="num">{fmtMoney(r.amount)}</td>
                <td>
                  {r.single_bid ? <span className="badge" title="Solo un proveedor presentó oferta">Una sola oferta</span> : null}
                  {r.short_period ? <span className="badge" title="Menos días de lo habitual para ofertar">Plazo corto</span> : null}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={6} className="empty">No hay contratos con estos filtros. Prueba con otra palabra o quita un filtro.</td></tr>
            )}
            {loading && rows.length === 0 && (
              <tr><td colSpan={6} className="empty">Cargando datos en tu navegador…</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <nav className="pager" aria-label="Páginas">
        <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Anterior</button>
        <span>Página {fmtInt(page + 1)} de {fmtInt(pages)}</span>
        <button type="button" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Siguiente</button>
      </nav>
    </section>
  );
}
