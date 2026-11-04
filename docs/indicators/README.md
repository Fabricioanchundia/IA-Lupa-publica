# Risk indicators

Lupa Pública computes **risk signals**: patterns that research links to a higher risk of
irregularities and that are worth a closer look. **They are not evidence of wrongdoing.**
Every indicator has a methodology page with its rules, data coverage, legitimate causes
and limitations.

| Code | Indicator | Process level | Buyer level | Methodology |
|---|---|---|---|---|
| R003 | Short submission period | `gold.indicator_r003_short_period` | `gold.buyer_r003_summary` | [r003-short-period.md](r003-short-period.md) |
| R018 | Single bid received | `gold.indicator_r018_single_bid` | `gold.buyer_r018_summary` | [r018-single-bid.md](r018-single-bid.md) |
| LP01 | Unusual supplier concentration (own) | — | `gold.indicator_lp01_supplier_concentration` (buyer × CPC division) | [lp01-supplier-concentration.md](lp01-supplier-concentration.md) |
| LP02 | Unusually high unit price (own, **experimental**: not public yet) | `gold.indicator_lp02_unit_price` (item) | — | [lp02-unit-price.md](lp02-unit-price.md) |

R codes follow the Open Contracting Partnership's red flags as implemented in
[Cardinal](https://cardinal.readthedocs.io/en/latest/cli/indicators/), so results can be
checked against an independent implementation. LP codes are Lupa Pública's own
indicators, for patterns Cardinal does not cover.

## How buyers are compared (all indicators)

1. **Observed vs expected.** For each buyer, the expected number of flagged processes is
   the sum, over its processes, of the flag rate of **comparable processes from other
   buyers** (leave-one-out). "Comparable" depends on the indicator (procedure type, and
   for R018 also what is bought).
2. **Enough data.** Buyers with fewer than 20 evaluated processes are kept but marked
   `enough_data = false` and must not be ranked.
3. **Could it be chance?** `p_value` is the probability of seeing at least the observed
   number of flagged processes if the buyer behaved like comparable processes
   (Poisson distribution with mean = expected; a conservative approximation).
4. **Many buyers at once.** With 500+ buyers, about 5% would look unusual by chance alone
   at p < 0.05. `q_value` applies the Benjamini-Hochberg correction among buyers with
   enough data: flagging q < 0.05 keeps the expected share of false alarms among the
   flagged buyers at about 5% (var `fdr_alpha`).
5. **Never on one or two events.** `significant` also requires at least 3 flagged
   processes (var `min_flagged_for_significance`), however unlikely they look.

`significant = true` means: **more flagged processes than comparable ones, unlikely to be
chance.** It still does not say why. Context (urgency, specialized markets, remote areas,
electoral calendars) can explain it, and is what a reviewer should check first.

## How to communicate results

Use: "received a single bid in X of Y processes", "more than comparable processes",
"worth reviewing". Avoid: "corruption", "fraud", "suspicious", or any judgement about a
buyer, a supplier or a person.
