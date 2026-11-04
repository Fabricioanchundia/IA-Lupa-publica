// Plain-language wording for the risk signals. Neutral on purpose: a signal says
// "this deserves a look", never "this is wrong".
import type { Row } from "./db";
import { fmtInt, fmtTimes } from "./format";

export const PRIORITY: Record<string, { label: string; tone: string; help: string }> = {
  review_first: {
    label: "Revisar primero",
    tone: "p-high",
    help: "Dos o más señales, o una señal muy por encima de lo esperado.",
  },
  review: { label: "Revisar", tone: "p-mid", help: "Una señal clara." },
  no_signal: { label: "Sin señales", tone: "p-none", help: "Ninguna señal destaca frente a entidades parecidas." },
  insufficient_data: {
    label: "Pocos datos",
    tone: "p-na",
    help: "Muy pocos procesos para comparar con justicia.",
  },
};

export function PriorityBadge({ value }: { value: unknown }) {
  const p = PRIORITY[String(value)] ?? PRIORITY.insufficient_data!;
  return (
    <span className={`priority ${p.tone}`} title={p.help}>
      <span className="dot" aria-hidden="true" />
      {p.label}
    </span>
  );
}

const LEVEL: Record<string, string> = {
  high: "Señal alta",
  medium: "Señal media",
  low: "Diferencia pequeña",
  none: "Normal",
  signal: "Señal",
  insufficient_data: "Pocos datos",
};
export const levelLabel = (v: unknown) => LEVEL[String(v)] ?? "—";
export const isSignal = (v: unknown) => v === "high" || v === "medium" || v === "signal";

/** One short sentence per signal that a buyer has, for lists and cards. */
export function reasons(r: Row): string[] {
  const out: string[] = [];
  if (isSignal(r.r018_level)) {
    out.push(
      `Una sola oferta en ${fmtInt(r.r018_flagged)} de ${fmtInt(r.r018_evaluated)} procesos competitivos: ${fmtTimes(r.r018_ratio)} lo esperado.`,
    );
  }
  if (isSignal(r.r003_level)) {
    out.push(
      `Plazo corto para ofertar en ${fmtInt(r.r003_flagged)} de ${fmtInt(r.r003_evaluated)} procesos: ${fmtTimes(r.r003_ratio)} lo esperado.`,
    );
  }
  if (isSignal(r.lp01_level)) {
    const n = Number(r.lp01_flagged_cells ?? 0);
    out.push(
      `Un mismo proveedor gana una parte inusual de los contratos en ${fmtInt(n)} ${n === 1 ? "categoría" : "categorías"}.`,
    );
  }
  return out;
}

export const INDICATORS = [
  {
    id: "r018",
    name: "Una sola oferta",
    what: "Procesos competitivos en los que solo un proveedor se presentó.",
    why: "Con poca competencia el Estado puede pagar más. Comparamos con compras del mismo tipo y categoría.",
  },
  {
    id: "r003",
    name: "Plazo corto",
    what: "Procesos que dieron menos días de lo habitual para presentar ofertas.",
    why: "Un plazo muy corto puede dejar fuera a proveedores que no alcanzan a preparar su oferta.",
  },
  {
    id: "lp01",
    name: "Proveedor concentrado",
    what: "Un mismo proveedor gana una parte muy alta de los contratos de una entidad en una categoría.",
    why: "Puede tener explicaciones normales (un único distribuidor), por eso es una señal y no una conclusión.",
  },
];
