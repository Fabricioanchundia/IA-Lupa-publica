const EXAMPLES = [
  "¿Cuánto gastó el Municipio de Manta en obras en 2025?",
  "¿Qué hospitales tienen más contratos con una sola oferta?",
  "¿Qué proveedores ganan más contratos de medicamentos en Guayas?",
];

/** Phase 7 will turn a question in Spanish into a safe, read-only SQL query and explain
 *  the answer. Until then this page only shows what it will do. */
export default function Ask() {
  return (
    <section>
      <header className="page-head">
        <h1>Preguntar con IA <span className="soon">Próximamente</span></h1>
        <p>Escribe una pregunta en español y la respuesta saldrá de los mismos datos públicos de esta página.</p>
      </header>
      <div className="search ask">
        <input type="text" disabled placeholder="Esta función llegará en la siguiente fase del proyecto" aria-label="Pregunta" />
        <button type="button" disabled>Preguntar</button>
      </div>
      <h2 className="section-title">Preguntas que podrás hacer</h2>
      <ul className="examples">
        {EXAMPLES.map((e) => <li key={e}>{e}</li>)}
      </ul>
      <div className="grid-3">
        <article className="card explain">
          <h3>Respuestas con su fuente</h3>
          <p className="muted">Cada respuesta mostrará la consulta usada, para que cualquiera pueda comprobarla.</p>
        </article>
        <article className="card explain">
          <h3>Solo lectura</h3>
          <p className="muted">La IA podrá consultar los datos públicos, nunca cambiarlos.</p>
        </article>
        <article className="card explain">
          <h3>Mismas reglas de privacidad</h3>
          <p className="muted">Las personas naturales seguirán apareciendo solo como “Persona #…”.</p>
        </article>
      </div>
    </section>
  );
}
