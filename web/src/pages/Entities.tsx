import { useEffect, useMemo, useState } from "react";
import { query, type Row } from "../db";
import { fmtCompactMoney, fmtInt, fmtMoney, fmtMonth, fmtPercent, provinceName, str, titleCase } from "../format";
import { href, type Route } from "../router";
import { INDICATORS, PRIORITY, PriorityBadge, isSignal, levelLabel } from "../signals";

const PAGE_SIZE = 25;

export default function Entities({ route }: { route: Route }) {
  return route.id ? <BuyerProfile buyerId={route.id} /> : <BuyerList route={route} />;
}

function BuyerList({ route }: { route: Route }) {
  const [draft, setDraft] = useState(route.params.get("q") ?? "");
  const [text, setText] = useState(draft);
  const [province, setProvince] = useState(route.params.get("provincia") ?? "");
  const [priority, setPriority] = useState(route.params.get("prioridad") ?? "");
  const [page, setPage] = useState(0);
  const [provinces, setProvinces] = useState<string[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    query("select distinct buyer_region as v from buyers where buyer_region is not null order by 1").then((r) =>
      setProvinces(r.map((x) => str(x.v))),
    );
  }, []);
  useEffect(() => {
    const id = setTimeout(() => { setText(draft); setPage(0); }, 250);
    return () => clearTimeout(id);
  }, [draft]);

  const [clause, params] = useMemo((): [string, unknown[]] => {
    const parts: string[] = [];
    const values: unknown[] = [];
    if (text.trim()) { parts.push("b.buyer_name ilike ?"); values.push(`%${text.trim()}%`); }
    if (province) { parts.push("b.buyer_region = ?"); values.push(province); }
    if (priority) { parts.push("coalesce(rp.review_priority, 'insufficient_data') = ?"); values.push(priority); }
    return [parts.length ? `where ${parts.join(" and ")}` : "", values];
  }, [text, province, priority]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const from = `
      from buyers as b
      left join review_priority as rp on b.buyer_id = rp.buyer_id
      left join (select buyer_id, count(*) as processes, sum(amount) as amount from processes group by 1) as s
        on b.buyer_id = s.buyer_id
      ${clause}`;
    Promise.all([
      query(`select count(*) as n ${from}`, params),
      query(
        `select b.buyer_id, b.buyer_name, b.buyer_region, s.processes, s.amount,
                coalesce(rp.review_priority, 'insufficient_data') as review_priority
         ${from}
         order by case coalesce(rp.review_priority, 'insufficient_data')
                    when 'review_first' then 0 when 'review' then 1 when 'no_signal' then 2 else 3 end,
                  s.amount desc nulls last
         limit ${PAGE_SIZE} offset ?`,
        [...params, page * PAGE_SIZE],
      ),
    ]).then(([n, r]) => {
      if (cancelled) return;
      setTotal(Number(n[0]?.n ?? 0));
      setRows(r);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [clause, params, page]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section>
      <header className="page-head">
        <h1>Entidades</h1>
        <p>Municipios, hospitales, ministerios… Busca una institución y abre su ficha.</p>
      </header>
      <div className="search">
        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Nombre de la institución: Manta, hospital, ministerio…"
          aria-label="Buscar entidades"
        />
      </div>
      <div className="filters">
        <label>Provincia
          <select value={province} onChange={(e) => { setProvince(e.target.value); setPage(0); }}>
            <option value="">Todas</option>
            {provinces.map((p) => <option key={p} value={p}>{provinceName(p)}</option>)}
          </select>
        </label>
        <label>Prioridad de revisión
          <select value={priority} onChange={(e) => { setPriority(e.target.value); setPage(0); }}>
            <option value="">Todas</option>
            {Object.entries(PRIORITY).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </label>
        <p className="muted small count">{fmtInt(total)} entidades</p>
      </div>

      <div className={`table-card${loading ? " is-loading" : ""}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">Entidad</th>
              <th scope="col" className="num">Procesos</th>
              <th scope="col" className="num">Monto</th>
              <th scope="col">Prioridad</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={str(r.buyer_id)}>
                <td>
                  <a href={href("entidades", str(r.buyer_id))}>{titleCase(r.buyer_name)}</a>
                  <small>{provinceName(r.buyer_region)}</small>
                </td>
                <td className="num">{fmtInt(r.processes ?? 0)}</td>
                <td className="num">{fmtCompactMoney(r.amount ?? 0)}</td>
                <td><PriorityBadge value={r.review_priority} /></td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={4} className="empty">No encontramos entidades con esa búsqueda.</td></tr>
            )}
            {loading && rows.length === 0 && (
              <tr><td colSpan={4} className="empty">Cargando datos en tu navegador…</td></tr>
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

type Profile = { buyer: Row | undefined; stats: Row; priority: Row | undefined; lp01: Row[]; top: Row[] };

function BuyerProfile({ buyerId }: { buyerId: string }) {
  const [data, setData] = useState<Profile>();

  useEffect(() => {
    Promise.all([
      query("select * from buyers where buyer_id = ?", [buyerId]),
      query(
        `select count(*) as processes, sum(amount) as amount,
                count(*) filter (where method in ('open', 'selective', 'limited')) as competitive,
                count(*) filter (where single_bid) as single_bid,
                min(month) as first_month, max(month) as last_month
         from processes where buyer_id = ?`,
        [buyerId],
      ),
      query("select * from review_priority where buyer_id = ?", [buyerId]),
      query(
        `select f.*, c.name as category from lp01_flags as f
         left join cpc_divisions as c on f.cpc_division = c.cpc_division
         where f.buyer_id = ? order by f.top_share desc`,
        [buyerId],
      ),
      query(
        `select p.ocid, p.month, p.title, p.amount, p.procedure, p.supplier_label, p.single_bid, p.short_period
         from processes as p where p.buyer_id = ? order by p.amount desc nulls last limit 8`,
        [buyerId],
      ),
    ]).then(([b, s, rp, lp01, top]) => setData({ buyer: b[0], stats: s[0] ?? {}, priority: rp[0], lp01, top }));
  }, [buyerId]);

  if (!data) return <p className="muted">Cargando ficha…</p>;
  if (!data.buyer) {
    return (
      <section>
        <p><a href={href("entidades")}>← Entidades</a></p>
        <h1>No encontramos esta entidad</h1>
      </section>
    );
  }
  const { buyer, stats, priority: rp, lp01, top } = data;

  const cards = [
    {
      ...INDICATORS[0]!,
      level: rp?.r018_level,
      detail: r018Sentence(rp),
    },
    {
      ...INDICATORS[1]!,
      level: rp?.r003_level,
      detail: rp?.r003_evaluated
        ? `${fmtInt(rp.r003_flagged)} de ${fmtInt(rp.r003_evaluated)} procesos con plazo corto: ${Number(rp.r003_ratio ?? 0).toFixed(1).replace(".", ",")} veces lo esperado.`
        : "No hay suficientes procesos con plazo publicado para comparar.",
    },
    {
      ...INDICATORS[2]!,
      level: rp?.lp01_level,
      detail: rp?.lp01_cells_evaluated
        ? `${fmtInt(rp.lp01_flagged_cells ?? 0)} de ${fmtInt(rp.lp01_cells_evaluated)} categorías con un proveedor que gana mucho más de lo típico.`
        : "No hay suficientes adjudicaciones por categoría para comparar.",
    },
  ];

  return (
    <section>
      <p className="crumbs"><a href={href("entidades")}>← Entidades</a></p>
      <header className="profile-head">
        <div>
          <h1>{titleCase(buyer.buyer_name)}</h1>
          <p className="muted">
            {provinceName(buyer.buyer_region)} · {fmtMonth(stats.first_month)} a {fmtMonth(stats.last_month)}
          </p>
        </div>
        <PriorityBadge value={rp?.review_priority ?? "insufficient_data"} />
      </header>

      <div className="tiles">
        <div className="tile"><strong>{fmtInt(stats.processes)}</strong><span>procesos</span></div>
        <div className="tile"><strong>{fmtCompactMoney(stats.amount)}</strong><span>monto total</span></div>
        <div className="tile">
          <strong>{Number(stats.competitive) ? fmtPercent(Number(stats.single_bid) / Number(stats.competitive)) : "—"}</strong>
          <span>de sus procesos competitivos con una sola oferta</span>
        </div>
      </div>

      <h2 className="section-title">Señales frente a entidades parecidas</h2>
      <div className="grid-3">
        {cards.map((c) => (
          <article key={c.id} className={`card indicator${isSignal(c.level) ? " has-signal" : ""}`}>
            <header className="card-head">
              <h3>{c.name}</h3>
              <span className={`level ${isSignal(c.level) ? "level-on" : ""}`}>{levelLabel(c.level)}</span>
            </header>
            <p>{c.detail}</p>
            <p className="muted small">{c.what}</p>
          </article>
        ))}
      </div>

      {lp01.length > 0 && (
        <>
          <h2 className="section-title">Categorías con proveedor concentrado</h2>
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th scope="col">Categoría</th>
                  <th scope="col">Proveedor que más gana</th>
                  <th scope="col" className="num">Contratos</th>
                  <th scope="col" className="num">Le gana</th>
                  <th scope="col" className="num">Lo típico</th>
                </tr>
              </thead>
              <tbody>
                {lp01.map((r) => (
                  <tr key={`${str(r.cpc_division)}-${str(r.supplier_label)}`}>
                    <td>{str(r.category) || `Categoría ${str(r.cpc_division)}`}</td>
                    <td>{titleCase(r.supplier_label)}</td>
                    <td className="num">{fmtInt(r.cell_awards)}</td>
                    <td className="num">{fmtPercent(r.top_share)}</td>
                    <td className="num">{fmtPercent(r.typical_top_share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <header className="card-head section-title">
        <h2>Sus contratos más grandes</h2>
        <a href={href("contratos", "", { entidad: buyerId })}>Ver todos sus contratos →</a>
      </header>
      <div className="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Mes</th>
              <th scope="col">Descripción</th>
              <th scope="col" className="num">Monto</th>
              <th scope="col">Señales</th>
            </tr>
          </thead>
          <tbody>
            {top.map((r) => (
              <tr key={str(r.ocid)}>
                <td className="nowrap">{fmtMonth(r.month)}</td>
                <td className="desc">
                  {str(r.title) || "Sin descripción"}
                  <small>{[str(r.procedure), r.supplier_label ? `Proveedor: ${titleCase(r.supplier_label)}` : ""].filter(Boolean).join(" · ")}</small>
                </td>
                <td className="num">{fmtMoney(r.amount)}</td>
                <td>
                  {r.single_bid ? <span className="badge">Una sola oferta</span> : null}
                  {r.short_period ? <span className="badge">Plazo corto</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small disclaimer">
        Las señales comparan a esta entidad con otras que compran cosas parecidas. Una señal indica dónde mirar
        con más atención; no prueba ninguna irregularidad.
      </p>
    </section>
  );
}

function r018Sentence(rp: Row | undefined): string {
  if (!rp?.r018_evaluated) return "No hay suficientes procesos competitivos para comparar.";
  const ratio = Number(rp.r018_ratio ?? 0).toFixed(1).replace(".", ",");
  return `${fmtInt(rp.r018_flagged)} de ${fmtInt(rp.r018_evaluated)} procesos competitivos recibieron una sola oferta: ${ratio} veces lo esperado para compras parecidas.`;
}
