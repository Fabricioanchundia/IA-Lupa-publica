const REPO = "https://github.com/Fabricioanchundia/Lupa-publica";

/** What the project is, how to read it, and how to ask for a correction (right of reply). */
export default function About() {
  return (
    <section className="about">
      <header className="page-head">
        <h1>Acerca de</h1>
        <p>Qué es Lupa Pública, de dónde salen los datos y cómo pedir una corrección.</p>
      </header>

      <div className="grid-2">
        <article className="card">
          <h2>Qué es</h2>
          <p>
            Lupa Pública es un proyecto independiente que hace más fácil revisar la contratación pública del Ecuador.
            No compra ni vende nada: las compras del Estado se hacen en el portal del SERCOP.
          </p>
          <p>
            Las <strong>señales</strong> comparan a cada institución con otras que compran cosas parecidas. Una señal
            indica dónde vale la pena mirar con más atención; <strong>no prueba ninguna irregularidad</strong>.
          </p>
          <p>
            <a href={`${REPO}/tree/main/docs/indicators`} target="_blank" rel="noopener noreferrer">
              Ver cómo se calcula cada señal →
            </a>
          </p>
        </article>

        <article className="card">
          <h2>De dónde salen los datos</h2>
          <p>
            De los datos abiertos que publica el SERCOP en el estándar internacional OCDS (Open Contracting Data
            Standard). Lupa Pública los descarga, los ordena y calcula las señales.
          </p>
          <p>
            Todo se calcula en tu navegador: no hay servidor, no usamos cookies ni herramientas de seguimiento, y
            nadie ve lo que buscas.
          </p>
        </article>

        <article className="card">
          <h2>Privacidad</h2>
          <p>
            Las personas naturales que le venden al Estado nunca aparecen con su nombre ni su cédula: se muestran como
            “Persona #” y un código. Antes de publicar, un control automático revisa que no se cuele ningún número de
            identificación personal.
          </p>
        </article>

        <article className="card contact">
          <h2>¿Algo está mal? Escríbenos</h2>
          <p>
            Si representas a una institución y crees que una señal está mal explicada, o encontraste un error en los
            datos, cuéntanos. Revisamos cada pedido y, si corresponde, corregimos y lo dejamos registrado.
          </p>
          <p className="actions">
            <a
              className="button"
              href={`${REPO}/issues/new?template=correccion.yml`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Pedir una corrección
            </a>
            <a href={`${REPO}/issues`} target="_blank" rel="noopener noreferrer">
              Ver pedidos anteriores
            </a>
          </p>
          <p className="muted small">Se abre en GitHub; necesitas una cuenta gratuita. Lo que escribas será público.</p>
        </article>
      </div>

      <p className="muted small disclaimer">
        Hecho por Fabricio Anchundia (Manta, Ecuador) ·{" "}
        <a href={REPO} target="_blank" rel="noopener noreferrer">código abierto en GitHub</a>
      </p>
    </section>
  );
}
