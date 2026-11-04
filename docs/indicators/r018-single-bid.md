# R018: Single bid received

> **A risk signal, not evidence of wrongdoing.** It points to processes worth a closer
> look. Many single bids have legitimate causes.

- **Code and definition:** R018 from the Open Contracting Partnership's red flags, as
  implemented in [Cardinal](https://cardinal.readthedocs.io/en/latest/cli/indicators/R/018.html):
  a process is flagged if it received exactly one bid and its procurement method is competitive.
- **Rationale (Cardinal):** "In a competitive procedure, a lack of competition might
  correspond to a suppression of competition."
- **Models:** `gold.indicator_r018_single_bid` (one row per evaluated process) and
  `gold.buyer_r018_summary` (one row per buyer).

## Which processes are evaluated

| Rule | Why |
|---|---|
| `procurement_method` in `open`, `selective` (dbt var `r018_procurement_methods`) | Cardinal's default. In Ecuador `selective` with bids is *Menor Cuantía*. Direct awards have one supplier **by design**: including them would add about 9,000 false signals. |
| The process has at least one award | The competition is over. Stricter than Cardinal, to avoid flagging processes that are still being evaluated. |
| `number_of_tenderers` is known (≥ 1) | SERCOP only publishes it for some procedure types; catalogue purchases have none. |

`limited` (*Lista corta*, consultancy with invited firms) is not evaluated by default:
it is competitive only among the invited firms. It can be added through the dbt var.

## What the data shows (24 months, Nov 2024 – Oct 2026)

| Procedure type | Processes with bids reported | Single bid |
|---|---:|---:|
| Subasta Inversa Electrónica (open) | 34,396 | 17.8% |
| Licitación (open) | 8,588 | 21.6% |
| Menor Cuantía (selective) | 4,266 | 31.5% |
| Cotización (open) | 1,919 | 22.6% |
| Concurso público (open) | 1,453 | 26.0% |
| Licitación de Seguros (open) | 1,327 | 36.5% |

Awarded and evaluated: 41,314 open and 4,141 selective processes; 7,879 and 1,318 of them
(19.1% and 31.8%) received a single bid. The monthly rate is stable (about 16–22%);
months with very few processes (January, and the latest month) swing much more.

## Comparing buyers fairly

A raw single-bid rate would penalize buyers for **what** they buy and **how**: insurance
tenders have 36.5% single bids everywhere, and specialized goods attract few suppliers.
So `buyer_r018_summary` computes an **expected** number of single bids: for each of the
buyer's processes, the single-bid rate of comparable processes, added up.

"Comparable", from most to least specific:

1. Same procedure type **and** same CPC division (`main_cpc_division`: first 2 digits of
   the CPC code of the process's most valuable item, from `int_process_main_cpc`).
2. If that group is too small, the same procedure type.
3. Otherwise, all evaluated processes.

A group is used only if **other buyers** have at least 30 processes in it (dbt var
`r018_min_baseline`).

**Leave-one-out:** the expected rate always comes from **other** buyers. Otherwise a
specialized buyer that dominates its own group (e.g. the only big buyer of military
textiles) would be compared mostly with itself and always look "normal". A dbt unit
test (`r018_buyers_are_compared_with_others_only`) checks this rule.

Output columns:

- `observed_to_expected`: single bids / expected single bids. Above 1 means more single
  bids than comparable processes of other buyers.
- `observed_to_expected_by_type`: the same, comparing only by procedure type (v1), to
  show how much the CPC adjustment changes the picture.
- `cpc_baseline_share`: share of the buyer's processes compared at the CPC level.
- `enough_data`: true only with at least 20 evaluated processes (dbt var
  `r018_min_processes`). One process with one bid is a 100% rate and means nothing.
  **Rankings and maps must only use buyers with `enough_data = true`.**

## Legitimate causes of a single bid

- Small or specialized markets (few suppliers in the country or the province).
- Very specific technical requirements (which can also be a way to restrict competition:
  that is why the signal exists).
- Low-value processes that do not attract bidders.
- Insurance and other concentrated markets.

## Limitations

- SERCOP publishes the **number** of bids, not the bids themselves, so we cannot check
  disqualifications (Cardinal R035, R036, R038) or bid prices (R024, R028, R058).
- `procurementMethod` is SERCOP's mapping to OCDS; `procurementMethodDetails` is the
  Ecuadorian procedure name and is what we use to compare like with like.
- Processes without an award are not evaluated, including processes declared void
  (*desierto*) after a single bid.
- The most recent months are provisional (see ADR-0001): some processes are not yet awarded.
- The buyer's province is where the entity is registered, not necessarily where the
  money is spent.

## How to communicate it

Use: "received a single bid", "less competition than comparable processes",
"worth reviewing". Avoid: "corruption", "fraud", "suspicious", or any judgement about
the buyer or the supplier.
