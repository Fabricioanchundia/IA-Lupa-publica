// SQL pieces shared by several pages. They are our own constants: user input never
// goes here, it is always passed as a query parameter.

/** Processes that the single-bid indicator (R018) can judge: competitive methods
 *  (dbt var r018_procurement_methods) with at least one bid reported. Same rule as the
 *  indicator, so the percentages here match the entity signals. */
export const R018_EVALUATED = (p = "p") => `(${p}.method in ('open', 'selective') and ${p}.tenderers >= 1)`;

/** SERCOP's procedure text can carry a whole framework agreement description
 *  ("Catálogo electrónico - Gran compra ... en el convenio SERCOP-..., SERVICIO DE ...").
 *  Keep only the procedure name so the table and the filter stay readable. */
export const PROCEDURE = (p = "p") =>
  `nullif(trim(split_part(regexp_replace(coalesce(${p}.procedure, ''), '\\s+en el convenio.*$', '', 'i'), ',', 1)), '')`;
