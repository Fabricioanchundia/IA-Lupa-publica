import { useEffect, useState, type FormEvent } from "react";
import MonthlyBars from "../components/MonthlyBars";
import { query, type Row } from "../db";
import { fmtCompactMoney, fmtInt, fmtMonth, fmtPercent, provinceName, titleCase } from "../format";
import { href } from "../router";
import { INDICATORS, PriorityBadge, reasons } from "../signals";

type Data = { kpi: Row; monthly: Row[]; first: Row[]; counts: Row[] };

export default function Home() {
  const [data, setData] = useState<Data>();
  const [text, setText] = useState("");

  useEffect(() => {
    Promise.all([
      query(`
        select count(*) as processes,
               sum(amount) as amount,
               count(*) filter (where method in ('open', 'selective', 'limited')) as competitive,
               count(*) filter (where single_bid) as single_bid,
               min(month) as first_month,
               max(month) as last_month
        from processes`),
      query("select source_month as month, processes from monthly_coverage order by 1"),
      query(`select * from review_priority where review_priority = 'review_first'
             order by signals desc, greatest(coalesce(r018_ratio, 0), coalesce(r003_ratio, 0)) desc`),
      query("select review_priority, count(*) as n from review_priority group by 1"),
    ]).then(([kpi, monthly, first, counts]) => setData({ kpi: kpi[0] ?? {}, monthly, first, counts }));
  }, []);

  const search = (e: FormEvent) => {
    e.preventDefault();
    window.location.hash = href("contratos", "", { q: text.trim() });
  };
  const count = (p: string) => Number(data?.counts.find((c) => c.review_priority === p)?.n ?? 0);
  const k = data?.kpi;

  return (
    <section>
      <header className="hero">
        <p className="eyebrow">Datos abiertos del SERCOP{k ? ` · ${fmtMonth(k.first_month)} a ${fmtMonth(k.last_month)}` : ""}</p>
        <h1>La contratación pública del Ecuador, fácil de revisar</h1>
        <p className="lede">
          Busca cualquier contrato, mira la ficha de cada institución y descubre dónde vale la pena mirar con
          más atención. Las señales ayudan a priorizar una revisión; <strong>no son acusaciones</strong>.
        </p>
        <form className="search hero-search" onSubmit={search} role="search">
          <input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="¿Qué buscas? Medicamentos, alcantarillado, Manta…"
            aria-label="Buscar contratos"
          />
          <button type="submit">Buscar</button>
        </form>
      </header>

      <div className="tiles">
        <Tile value={fmtInt(k?.processes)} label="procesos de contratación" />
        <Tile value={fmtCompactMoney(k?.amount)} label="monto adjudicado o presupuestado" />
        <Tile
          value={k ? fmtPercent(Number(k.single_bid) / Math.max(1, Number(k.competitive))) : "—"}
          label="de los procesos competitivos recibió una sola oferta"
        />
        <Tile value={data ? fmtInt(count("review_first")) : "—"} label="entidades para revisar primero" accent />
      </div>

      <div className="grid-2">
        <article className="card">
          <header className="card-head">
            <h2>Para revisar primero</h2>
            <a href={href("entidades", "", { prioridad: "review_first" })}>Ver todas</a>
          </header>
          <p className="muted">
            Instituciones con varias señales o con una señal muy por encima de lo esperado. Además hay{" "}
            {fmtInt(count("review"))} con una señal.
          </p>
          <ol className="review-list">
            {data?.first.slice(0, 6).map((r) => (
              <li key={String(r.buyer_id)}>
                <a href={href("entidades", String(r.buyer_id))}>
                  <span className="name">{titleCase(r.buyer_name)}</span>
                  <small>{provinceName(r.buyer_region)}</small>
                </a>
                <ul>
                  {reasons(r).map((reason) => <li key={reason}>{reason}</li>)}
                </ul>
              </li>
            ))}
            {!data && <li className="skeleton">Cargando datos en tu navegador…</li>}
          </ol>
        </article>

        <article className="card">
          <header className="card-head">
            <h2>Procesos publicados por mes</h2>
          </header>
          {data ? (
            <MonthlyBars
              label="Procesos"
              data={data.monthly.map((m) => ({ month: String(m.month), value: Number(m.processes) }))}
            />
          ) : (
            <div className="skeleton chart-skeleton">Cargando…</div>
          )}
          <p className="muted small">
            Cada barra es un mes. Pasa el cursor para ver el número exacto.
          </p>
        </article>
      </div>

      <h2 className="section-title">Cómo leer las señales</h2>
      <div className="grid-3">
        {INDICATORS.map((i) => (
          <article className="card explain" key={i.id}>
            <h3>{i.name}</h3>
            <p>{i.what}</p>
            <p className="muted">{i.why}</p>
          </article>
        ))}
      </div>
      <p className="muted small legend-row">
        Cómo se decide la prioridad: <PriorityBadge value="review_first" /> <PriorityBadge value="review" />{" "}
        <PriorityBadge value="no_signal" /> <PriorityBadge value="insufficient_data" />
      </p>
    </section>
  );
}

function Tile({ value, label, accent = false }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className={`tile${accent ? " tile-accent" : ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
