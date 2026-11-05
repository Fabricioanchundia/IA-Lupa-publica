import { useMemo, useState } from "react";
import gallery from "../askExamples.json";
import { query } from "../db";
import { str } from "../format";

type Example = {
  question: string;
  refusal: string | null;
  sql: string | null;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  explanation: string;
  unverified_numbers: string[];
};

const EXAMPLES = gallery.examples as Example[];
const REPO = "https://github.com/Fabricioanchundia/Lupa-publica";
const number = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 2 });

const cell = (v: unknown) =>
  typeof v === "number" ? number.format(v) : typeof v === "boolean" ? (v ? "sí" : "no") : str(v);

/** Phase 7 gallery: questions answered by the AI on the developer's computer (free, no
 *  server). Each answer shows its SQL, and the visitor can re-run it here, in the
 *  browser, on the same public data to check the numbers. */
export default function Ask() {
  const [filter, setFilter] = useState("");
  const [index, setIndex] = useState(0);
  const shown = useMemo(
    () => EXAMPLES.filter((e) => e.question.toLowerCase().includes(filter.trim().toLowerCase())),
    [filter],
  );
  const current = shown[Math.min(index, Math.max(0, shown.length - 1))];

  return (
    <section className="ask-page">
      <header className="page-head">
        <h1>Preguntar con IA <span className="soon">Demo</span></h1>
        <p>
          Preguntas en español respondidas por una IA que traduce cada pregunta a una consulta sobre los datos
          públicos. Los números salen siempre de los datos, nunca de la memoria de la IA.
        </p>
      </header>

      <ol className="how">
        <li><strong>La IA escribe la consulta</strong> a partir de la pregunta.</li>
        <li><strong>Dos candados la revisan:</strong> solo puede leer, y solo los datos públicos.</li>
        <li><strong>Los datos responden</strong> y la IA resume el resultado en palabras simples.</li>
      </ol>

      {EXAMPLES.length === 0 ? (
        <p className="status">Todavía no hay ejemplos publicados.</p>
      ) : (
        <div className="ask-layout">
          <aside className="card ask-list">
            <input
              type="search"
              value={filter}
              onChange={(e) => { setFilter(e.target.value); setIndex(0); }}
              placeholder="Filtrar preguntas…"
              aria-label="Filtrar preguntas"
            />
            <ul>
              {shown.map((e, i) => (
                <li key={e.question}>
                  <button
                    type="button"
                    aria-current={current === e ? "true" : undefined}
                    onClick={() => setIndex(i)}
                  >
                    {e.refusal ? "🔒 " : ""}{e.question}
                  </button>
                </li>
              ))}
            </ul>
          </aside>
          {current && <AnswerCard key={current.question} example={current} />}
        </div>
      )}

      <p className="muted small disclaimer">
        Respuestas generadas el {gallery.generated_at || "—"} con el modelo abierto {gallery.model || "—"}, que corre en
        la computadora del autor (sin costo y sin enviar datos a nadie) y revisadas por una persona. Para hacer tus
        propias preguntas, usa el comando <code>lupa ask</code> del{" "}
        <a href={REPO} target="_blank" rel="noopener noreferrer">proyecto en GitHub</a>.
      </p>
    </section>
  );
}

function AnswerCard({ example }: { example: Example }) {
  const [live, setLive] = useState<{ columns: string[]; rows: unknown[][] } | null>(null);
  const [state, setState] = useState<"idle" | "running" | "error">("idle");

  if (example.refusal) {
    return (
      <article className="card answer">
        <p className="eyebrow-q">Pregunta</p>
        <h2>{example.question}</h2>
        <div className="refusal">
          <strong>🔒 La IA se negó a responder.</strong>
          <p>{example.refusal}</p>
          <p className="muted small">
            Aunque hubiera intentado algo así, los candados lo habrían bloqueado: solo se permiten consultas de lectura
            sobre los datos públicos, que no contienen nombres ni cédulas de personas.
          </p>
        </div>
      </article>
    );
  }

  const runLive = async () => {
    setState("running");
    try {
      const rows = await query(example.sql ?? "");
      const columns = rows.length ? Object.keys(rows[0]!) : example.columns;
      setLive({ columns, rows: rows.map((r) => columns.map((c) => r[c])) });
      setState("idle");
    } catch {
      setState("error");
    }
  };

  const table = live ?? { columns: example.columns, rows: example.rows };

  return (
    <article className="card answer">
      <p className="eyebrow-q">Pregunta</p>
      <h2>{example.question}</h2>

      {example.explanation && (
        <div className="summary">
          <p>{example.explanation}</p>
          <small>Resumen escrito por IA. La tabla de abajo es el dato exacto.</small>
          {example.unverified_numbers.length > 0 && (
            <small className="warn">
              ⚠️ El resumen menciona números que no están en la tabla ({example.unverified_numbers.join(", ")}). Confía
              en la tabla.
            </small>
          )}
        </div>
      )}

      <div className="table-card">
        <table>
          <thead>
            <tr>{table.columns.map((c) => <th key={c} scope="col">{c.replaceAll("_", " ")}</th>)}</tr>
          </thead>
          <tbody>
            {table.rows.map((row, i) => (
              <tr key={i}>
                {row.map((v, j) => (
                  <td key={j} className={typeof v === "number" ? "num" : undefined}>{cell(v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!live && example.row_count > example.rows.length && (
        <p className="muted small">Se muestran {example.rows.length} de {example.row_count} filas.</p>
      )}

      <div className="actions">
        <button type="button" className="button" onClick={runLive} disabled={state === "running"}>
          {state === "running" ? "Calculando…" : live ? "Calculado en tu navegador ✓" : "Comprobar en vivo"}
        </button>
        {state === "error" && <span className="muted small">No se pudo ejecutar con los datos actuales.</span>}
        {live && <span className="muted small">Este resultado se calculó ahora mismo, en tu navegador.</span>}
      </div>

      <details className="sql">
        <summary>Ver la consulta SQL</summary>
        <pre><code>{example.sql}</code></pre>
      </details>
    </article>
  );
}
