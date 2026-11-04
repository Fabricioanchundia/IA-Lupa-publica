import { useEffect, useState, type ReactNode } from "react";
import { whenReady } from "./db";
import About from "./pages/About";
import Ask from "./pages/Ask";
import Contracts from "./pages/Contracts";
import Entities from "./pages/Entities";
import Home from "./pages/Home";
import MapPage from "./pages/MapPage";
import { useRoute, type Route } from "./router";

type Section = { id: string; label: string; hint: string; view: (route: Route) => ReactNode };

const SECTIONS: Section[] = [
  { id: "inicio", label: "Inicio", hint: "Resumen y entidades para revisar", view: () => <Home /> },
  { id: "contratos", label: "Contratos", hint: "Buscar y filtrar procesos", view: (r) => <Contracts route={r} /> },
  { id: "entidades", label: "Entidades", hint: "Ficha de cada institución", view: (r) => <Entities route={r} /> },
  { id: "mapa", label: "Mapa", hint: "Cifras por provincia", view: () => <MapPage /> },
  { id: "preguntar", label: "Preguntar con IA", hint: "Consultas en español", view: () => <Ask /> },
  { id: "acerca", label: "Acerca de", hint: "Datos, privacidad y contacto", view: () => <About /> },
];

export default function App() {
  const route = useRoute();
  const section = SECTIONS.find((s) => s.id === route.page) ?? SECTIONS[0]!;
  const [status, setStatus] = useState<"loading" | "ready" | string>("loading");

  useEffect(() => {
    whenReady()
      .then(() => setStatus("ready"))
      .catch((e: unknown) => setStatus(String(e instanceof Error ? e.message : e)));
  }, []);

  return (
    <div className="shell">
      <a className="skip" href="#main">Saltar al contenido</a>
      <aside className="sidebar">
        <a className="brand" href="#/inicio">
          <span className="brand-mark" aria-hidden="true" />
          Lupa Pública
        </a>
        <nav aria-label="Secciones">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#/${s.id}`} aria-current={section.id === s.id ? "page" : undefined}>
              <span>{s.label}</span>
              <small>{s.hint}</small>
            </a>
          ))}
        </nav>
        <p className="sidebar-note">
          Señales para priorizar la revisión, no acusaciones. Todo se calcula en tu navegador con datos abiertos del SERCOP.
        </p>
      </aside>
      {/* key: a new address (e.g. another entity) starts the page fresh. */}
      <main className="content" id="main" key={route.key}>
        {status === "loading" && (
          <p className="status" role="status">Cargando los datos en tu navegador… la primera vez tarda unos segundos.</p>
        )}
        {status !== "loading" && status !== "ready" && (
          <div className="status status-error" role="alert">
            <strong>No se pudieron cargar los datos.</strong> Si estás probando en tu computadora, ejecuta primero{" "}
            <code>uv run lupa export-public</code>.<small>{status}</small>
          </div>
        )}
        {section.view(route)}
      </main>
    </div>
  );
}
