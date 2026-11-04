const integer = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat("es-EC", { style: "percent", maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("es-EC", { maximumFractionDigits: 1 });
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

export const fmtInt = (n: unknown) => (n == null ? "—" : integer.format(Number(n)));
export const fmtMoney = (n: unknown) => (n == null ? "—" : `US$ ${integer.format(Number(n))}`);
/** 12_936_400_000 -> "US$ 12,9 mil M", 152_300_000 -> "US$ 152,3 M", 737_200 -> "US$ 737,2 mil" */
export const fmtCompactMoney = (n: unknown) => {
  if (n == null) return "—";
  const v = Number(n);
  if (Math.abs(v) >= 1e9) return `US$ ${decimal.format(v / 1e9)} mil M`;
  if (Math.abs(v) >= 1e6) return `US$ ${decimal.format(v / 1e6)} M`;
  if (Math.abs(v) >= 1e3) return `US$ ${decimal.format(v / 1e3)} mil`;
  return `US$ ${integer.format(v)}`;
};
export const fmtPercent = (n: unknown) => (n == null || Number.isNaN(Number(n)) ? "—" : percent.format(Number(n)));
export const fmtTimes = (n: unknown) => (n == null ? "—" : `${decimal.format(Number(n))} veces`);

/** "2025-03" -> "mar 2025" */
export const fmtMonth = (m: unknown) => {
  const [y, mm] = String(m ?? "").split("-");
  const i = Number(mm) - 1;
  return y && i >= 0 && i < 12 ? `${MONTHS[i]} ${y}` : String(m ?? "—");
};

// Small words stay lower case inside a name; acronyms and company types stay upper case.
const SMALL = new Set(["de", "del", "la", "las", "los", "el", "y", "e", "en", "para", "por", "a", "al"]);
const UPPER: [RegExp, string][] = [
  [/\bGad\b/g, "GAD"],
  [/\bEp\b/g, "EP"],
  [/\bS\.a\.s\.?/g, "S.A.S."],
  [/\bS\.a\./g, "S.A."],
  [/\bCia\.?/g, "Cía."],
  [/\bLtda\.?/g, "Ltda."],
  [/\bIess\b/g, "IESS"],
  [/\bCne\b/g, "CNE"],
];

/** SERCOP writes names in capitals: "GAD MUNICIPAL DE MANTA" -> "GAD Municipal de Manta". */
export const titleCase = (s: unknown) => {
  if (typeof s !== "string" || !s) return "—";
  let out = s
    .toLowerCase()
    .split(" ")
    .map((w, i) => (i > 0 && SMALL.has(w) ? w : w.replace(/(^|[(/-])\p{L}/gu, (c) => c.toUpperCase())))
    .join(" ");
  for (const [re, rep] of UPPER) out = out.replace(re, rep);
  return out;
};

// SERCOP spells provinces without accents.
const PROVINCES: Record<string, string> = {
  BOLIVAR: "Bolívar",
  GALAPAGOS: "Galápagos",
  "LOS RIOS": "Los Ríos",
  MANABI: "Manabí",
  SUCUMBIOS: "Sucumbíos",
  "SANTO DOMINGO DE LOS TSACHILAS": "Santo Domingo de los Tsáchilas",
};
export const provinceName = (s: unknown) =>
  typeof s === "string" && s && s !== "UNKNOWN" ? (PROVINCES[s] ?? titleCase(s)) : "Sin provincia";

export const str = (v: unknown) => (v == null ? "" : String(v));
