import { useEffect, useMemo, useState } from "react";
import { query, type Row } from "../db";
import { GALAPAGOS_INSET, PROVINCES, VIEWBOX } from "../ecuadorProvinces";
import { fmtCompactMoney, fmtInt, fmtPercent, provinceName, str, titleCase } from "../format";
import { href } from "../router";
import { PriorityBadge } from "../signals";

type Metric = { id: string; label: string; legend: string; format: (n: number) => string };

const METRICS: Metric[] = [
  { id: "processes", label: "Contratos", legend: "Número de procesos", format: (n) => fmtInt(Math.round(n)) },
  { id: "amount", label: "Monto", legend: "Monto total", format: (n) => fmtCompactMoney(n) },
  {
    id: "single_bid_rate",
    label: "Una sola oferta",
    legend: "% de procesos competitivos con una sola oferta",
    format: (n) => fmtPercent(n),
  },
  { id: "to_review", label: "Entidades a revisar", legend: "Entidades con prioridad Revisar o Revisar primero", format: (n) => fmtInt(Math.round(n)) },
];
const STEPS = 5;

/** Quantile breaks so each color holds about the same number of provinces. */
function breaks(values: number[]): number[] {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return [];
  return Array.from({ length: STEPS - 1 }, (_, i) => sorted[Math.floor(((i + 1) * sorted.length) / STEPS)]!);
}
const bin = (v: number, cuts: number[]) => cuts.filter((c) => v >= c).length;

export default function MapPage() {
  const [metric, setMetric] = useState<Metric>(METRICS[0]!);
  const [rows, setRows] = useState<Row[]>();
  const [hover, setHover] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [top, setTop] = useState<Row[]>([]);

  useEffect(() => {
    query(`
      with p as (
        select b.buyer_region as region, count(*) as processes, sum(p.amount) as amount,
               count(*) filter (where p.method in ('open', 'selective', 'limited')) as competitive,
               count(*) filter (where p.single_bid) as single_bid
        from processes as p join buyers as b on p.buyer_id = b.buyer_id
        where b.buyer_region is not null
        group by 1
      ),
      r as (
        select buyer_region as region,
               count(*) filter (where review_priority in ('review_first', 'review')) as to_review,
               count(*) filter (where review_priority = 'review_first') as review_first
        from review_priority group by 1
      )
      select p.*, p.single_bid / nullif(p.competitive, 0) as single_bid_rate,
             coalesce(r.to_review, 0) as to_review, coalesce(r.review_first, 0) as review_first
      from p left join r on p.region = r.region`).then(setRows);
  }, []);

  useEffect(() => {
    if (!selected) return setTop([]);
    query(
      `select b.buyer_id, b.buyer_name, coalesce(rp.review_priority, 'insufficient_data') as review_priority,
              sum(p.amount) as amount
       from processes as p join buyers as b on p.buyer_id = b.buyer_id
       left join review_priority as rp on b.buyer_id = rp.buyer_id
       where b.buyer_region = ?
       group by all order by amount desc nulls last limit 5`,
      [selected],
    ).then(setTop);
  }, [selected]);

  const byRegion = useMemo(() => new Map((rows ?? []).map((r) => [str(r.region), r])), [rows]);
  const value = (r: Row | undefined) => (r && r[metric.id] != null ? Number(r[metric.id]) : null);
  const cuts = useMemo(
    () => breaks((rows ?? []).map((r) => value(r)).filter((v): v is number => v != null)),
    [rows, metric],
  );
  const ranked = useMemo(
    () => [...(rows ?? [])].sort((a, b) => (value(b) ?? -1) - (value(a) ?? -1)),
    [rows, metric],
  );
  const focus = hover ?? selected;
  const focusRow = focus ? byRegion.get(focus) : undefined;

  return (
    <section>
      <header className="page-head">
        <h1>Mapa</h1>
        <p>Compara provincias según la provincia de la entidad que compra. Toca una provincia para ver el detalle.</p>
      </header>

      <div className="segmented" role="radiogroup" aria-label="Qué mostrar en el mapa">
        {METRICS.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={metric.id === m.id}
            onClick={() => setMetric(m)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="map-layout">
        <div className="card map-card">
          <svg viewBox={VIEWBOX} className="map" role="img" aria-label={`Mapa del Ecuador: ${metric.legend} por provincia`}>
            <rect
              className="inset"
              x={GALAPAGOS_INSET.x}
              y={GALAPAGOS_INSET.y}
              width={GALAPAGOS_INSET.width}
              height={GALAPAGOS_INSET.height}
              rx="8"
            />
            {PROVINCES.map((p) => {
              const r = byRegion.get(p.region);
              const v = value(r);
              const cls = v == null ? "no-data" : `q${bin(v, cuts)}`;
              return (
                <path
                  key={p.region}
                  d={p.d}
                  className={`prov ${cls}${focus === p.region ? " is-focus" : ""}`}
                  tabIndex={0}
                  role="button"
                  aria-label={`${p.name}: ${v == null ? "sin datos" : metric.format(v)}`}
                  onMouseEnter={() => setHover(p.region)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(p.region)}
                  onBlur={() => setHover(null)}
                  onClick={() => setSelected(p.region)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(p.region); } }}
                />
              );
            })}
            <text x={GALAPAGOS_INSET.x + 8} y={GALAPAGOS_INSET.y + GALAPAGOS_INSET.height + 18} className="map-note">
              Galápagos (desplazado)
            </text>
          </svg>
          <div className="legend" aria-hidden="true">
            <span className="legend-title">{metric.legend}</span>
            <div className="legend-scale">
              {Array.from({ length: STEPS }, (_, i) => (
                <span key={i} className={`swatch q${i}`} />
              ))}
            </div>
            <div className="legend-labels">
              <span>{rows ? metric.format(Math.min(...ranked.map((r) => value(r) ?? Infinity))) : ""}</span>
              <span>{rows ? metric.format(value(ranked[0]) ?? 0) : ""}</span>
            </div>
            <span className="legend-na"><span className="swatch no-data" /> Sin datos</span>
          </div>
        </div>

        <aside className="card side-panel" aria-live="polite">
          {focusRow ? (
            <>
              <h2>{provinceName(focus)}</h2>
              <dl className="facts">
                <div><dt>Contratos</dt><dd>{fmtInt(focusRow.processes)}</dd></div>
                <div><dt>Monto</dt><dd>{fmtCompactMoney(focusRow.amount)}</dd></div>
                <div><dt>Una sola oferta</dt><dd>{fmtPercent(focusRow.single_bid_rate)}</dd></div>
                <div><dt>Entidades a revisar</dt><dd>{fmtInt(focusRow.to_review)}</dd></div>
              </dl>
              {selected === focus && top.length > 0 && (
                <>
                  <h3>Entidades que más contratan</h3>
                  <ol className="mini-list">
                    {top.map((t) => (
                      <li key={str(t.buyer_id)}>
                        <a href={href("entidades", str(t.buyer_id))}>{titleCase(t.buyer_name)}</a>
                        <span>{fmtCompactMoney(t.amount)} <PriorityBadge value={t.review_priority} /></span>
                      </li>
                    ))}
                  </ol>
                </>
              )}
              <p className="actions">
                <a className="button" href={href("contratos", "", { provincia: focus ?? "" })}>Ver contratos</a>
                <a href={href("entidades", "", { provincia: focus ?? "" })}>Ver entidades</a>
              </p>
            </>
          ) : focus ? (
            <><h2>{provinceName(focus)}</h2><p className="muted">Sin datos para esta provincia.</p></>
          ) : (
            <>
              <h2>Elige una provincia</h2>
              <p className="muted">Pasa el cursor o toca una provincia del mapa para ver sus cifras.</p>
            </>
          )}
        </aside>
      </div>

      <h2 className="section-title">{metric.legend}, de mayor a menor</h2>
      <div className="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col">Provincia</th>
              <th scope="col" className="num">Contratos</th>
              <th scope="col" className="num">Monto</th>
              <th scope="col" className="num">Una sola oferta</th>
              <th scope="col" className="num">Entidades a revisar</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((r) => (
              <tr key={str(r.region)} className={selected === r.region ? "is-selected" : ""}>
                <td><button type="button" className="link-btn" onClick={() => setSelected(str(r.region))}>{provinceName(r.region)}</button></td>
                <td className="num">{fmtInt(r.processes)}</td>
                <td className="num">{fmtCompactMoney(r.amount)}</td>
                <td className="num">{fmtPercent(r.single_bid_rate)}</td>
                <td className="num">{fmtInt(r.to_review)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small disclaimer">
        Las entidades sin provincia publicada no aparecen en el mapa. Límites provinciales: Natural Earth (dominio público).
      </p>
    </section>
  );
}
