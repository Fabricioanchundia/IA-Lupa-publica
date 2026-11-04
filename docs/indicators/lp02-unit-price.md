# LP02: Unusually high unit price

> **Status: experimental.** Computed and tested, but **not shown in public outputs or
> rankings** until comparable products can be identified from item descriptions (see
> "Review of the first results").

> **A risk signal, not evidence of wrongdoing.** A high price can come from better
> quality, small quantities, transport to remote areas, urgency or a data entry error
> (e.g. a total entered as a unit price). `price_difference` is a difference against the
> typical price, **not** a proven overpayment.

- **Code:** LP02 is Lupa Pública's own indicator. Cardinal's price indicators compare
  bids within a process, which SERCOP does not publish; we compare unit prices across
  buyers instead.
- **Models:** `silver.int_comparable_items`, `gold.price_reference_groups` (one row per
  CPC code and unit) and `gold.indicator_lp02_unit_price` (one row per item in a usable
  group).

## Comparable items

Two items are compared only if they have the **same 9-digit CPC code and the same unit**
(a price "per box" is not a price "per unit"). Catalogue purchases are excluded: their
prices are set by the catalogue, and they use CPC codes of other lengths and no units.

In the exploration (24 months), outside the catalogue every priced item has a unit and
most have a 9-digit code. 3,100 groups have at least 10 items from at least 3 buyers
(546,467 items), but prices inside them are very spread: the median group has its 90th
percentile price **12 times** its 10th percentile, and 1,673 groups more than 10 times.

| Example group | Items | Buyers | 10th pct | Median | 90th pct | Spread |
|---|---:|---:|---:|---:|---:|---:|
| 532900011, UNIDAD (civil works) | 18,946 | 654 | 10.15 | 107.18 | 3,901.49 | 384× |
| 375100021, METRO CÚBICO | 10,936 | 396 | 122.74 | 181.75 | 274.10 | 2.2× |
| 545400311, METRO CÚBICO | 5,378 | 247 | 117.81 | 183.91 | 283.42 | 2.4× |

A code like "civil works, per UNIDAD" mixes very different things, so its prices cannot
be compared. Codes measured in cubic metres of a material are much more homogeneous.

## Method

1. **Reference price per group:** each buyer's median price in the group, then the median
   across buyers (in logarithms). Every buyer counts once, so a buyer with thousands of
   items cannot set the reference. A dbt unit test
   (`price_reference_is_not_set_by_the_biggest_buyer`) checks this.
2. **Usable groups:** at least 5 buyers and 10 items, and a spread (90th / 10th
   percentile of the buyers' median prices) of at most 5 (vars `lp02_min_buyers`,
   `lp02_min_items`, `lp02_max_spread`). Groups above that are not evaluated.
3. **Flagged item:** unit price at least **3 times** the reference price (var
   `lp02_min_ratio`) **and** a robust outlier: robust z-score (difference in log price
   divided by 1.4826 × MAD of the buyers' medians) of at least 3.5 (var
   `lp02_min_robust_z`, the usual Iglewicz–Hoaglin threshold). Median and MAD are used
   instead of mean and standard deviation because a few extreme prices would distort
   those.
4. `price_difference` = (unit price − reference price) × quantity, only for flagged items.

## Review of the first results (v1)

Over 24 months: 812 of 11,922 groups are usable (161,594 items); 3,670 items (2.3%) are
flagged, with a total difference against reference prices of USD 41.1 million.

The item descriptions behind the 15 largest differences (read from bronze only for this
review) show that **most are different products under the same CPC code and unit**:

| Group | Typical items (description) | Flagged items (description) |
|---|---|---|
| 363201011, METRO | PVC pipe 50–110 mm, USD 3–8 per metre | PVC sewer pipe 315–1,500 mm, USD 74–517 per metre |
| 532510014, METRO | PVC drain pipe 2–4 inches, USD 5–10 | PVC sewer pipe 1,200 mm, USD 300–526 |
| 441600012, METRO | hose 12 mm, PVC pipe 25–50 mm | structured-wall PVC pipe 800 mm |
| 375100021, METRO CUADRADO | concrete subfloor 5–8 cm thick | concrete pavement 18 cm thick |

A metre of 1,500 mm sewer pipe is a different product from a metre of 50 mm pipe. The
buyer-level spread filter does not catch this because most buyers buy small pipes, so
the group looks homogeneous. The CPC code and unit are **not enough** to define a
comparable product.

Only some flags look like true price differences for the same product (for example a
geotextile at about USD 22–25 per m² where the same material usually costs USD 2.3–2.5),
and they cannot be told apart from size differences without the description.

**Next step:** group items by **description** as well as CPC code and unit, for example
with text embeddings (planned for the AI phases). Descriptions are published with HTML
entities (`&oacute;`, `&Oslash;`) that must be decoded first.

## Limitations

- Even with the same code and unit, items can differ in brand, quality or specifications.
- Only high prices are flagged. Abnormally low prices (which can hide quality problems or
  later contract changes) are not covered yet.
- Groups with fewer than 5 buyers, and heterogeneous codes, are not evaluated.
- No adjustment for inflation over the 24 months, quantity discounts or transport costs.
- Ranking by `price_difference` puts large quantities of mismatched products first: it
  should never be used to rank buyers until comparable products are identified.
