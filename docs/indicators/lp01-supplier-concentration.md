# LP01: Unusual supplier concentration

> **A risk signal, not evidence of wrongdoing.** Some suppliers win often because they
> are the best, the closest or the only ones. This indicator only says that a buyer uses
> a supplier much more than comparable buyers do.

- **Code:** LP01 is Lupa Pública's own indicator. Cardinal has no equivalent; the idea
  (one supplier winning a large share of a buyer's contracts) is a classic red flag in
  procurement research.
- **Models:** `silver.int_buyer_supplier_wins` (awards and money per buyer, CPC division
  and supplier) and `gold.indicator_lp01_supplier_concentration` (one row per buyer and
  CPC division with enough awards).

## Why not just "top supplier share"

In the exploration (24 months), concentration depends mostly on **size**:

| Buyer size (awards) | Buyers | Median suppliers | Median top-supplier share of money | Top share > 50% |
|---|---:|---:|---:|---:|
| 1–9 | 1,982 | 2 | 69% | 1,460 |
| 10–49 | 1,563 | 11 | 40% | 545 |
| 50–199 | 1,512 | 23 | 34% | 362 |
| 200+ | 368 | 56 | 25% | 36 |

A buyer with three purchases is always "concentrated". Money shares are also driven by
one big contract (a road, a building). And some markets have a single provider. A raw
share would flag all of these.

## Method

1. **What is compared:** awards, not money, within the same **CPC division** (what is
   bought). Catalogue purchases are excluded, because the catalogue sets the supplier:
   `selective` without tenderers **and** procedure types named "Catálogo electrónico - …",
   which SERCOP publishes with method `direct`. Processes without a procurement method
   are excluded too. Consortium awards count 1/n for each supplier.
2. **Eligible cells:** a buyer with at least 10 awards in a CPC division
   (var `lp01_min_awards`).
3. **Top supplier:** the supplier with most awards in the cell, and its share.
4. **Expected share** is the **higher** of two references, both computed from **other**
   buyers (leave-one-out):
   - `typical_top_share`: the median top-supplier share of other buyers in the same CPC
     division (at least 5 of them, var `lp01_min_peer_cells`; otherwise the overall
     median). Some categories are concentrated everywhere, such as local food services.
   - `supplier_share_elsewhere`: how often this supplier wins from other buyers in the
     **same province** and CPC division (nationwide if they have fewer than 30 awards,
     var `lp01_min_baseline`), with +0.5/+1 smoothing. A market leader or sole provider
     wins a lot everywhere.
5. **Could it be chance?** Expected wins = cell awards × expected share. `p_value` =
   Poisson probability of at least the observed wins; `q_value` corrects for testing all
   cells at once (Benjamini-Hochberg), as for the other indicators (see
   [README](README.md)).
6. **Flagged** when q < 0.05 **and** the top supplier has at least half of the cell's
   awards (var `lp01_min_top_share`) **and** at least 3 wins.

A dbt unit test (`lp01_favourite_supplier_vs_market_leader`) checks the four situations:
a favourite supplier in a category where buyers usually spread their awards (flagged),
a buyer that spreads its awards, a market leader used by everyone, and a category where
every buyer uses one local supplier (none of these flagged).

## Version history

- **v1** compared the top supplier only with how often it wins elsewhere. It flagged
  201 of the 234 cells where one supplier had at least half of the awards (86%): in
  fragmented markets almost no supplier wins much elsewhere, so any concentration looked
  unusual. Its top results were local food services (CPC 63, where the median buyer
  already gives 47% to one supplier and the 90th percentile 98%) and associations of the
  popular and solidarity economy. It also let catalogue purchases published as `direct`
  through: 2,219 of the awards behind its flags. An indicator that flags almost every
  case does not help anyone prioritize, so v1 was not released.
- **v2** adds the typical concentration of the category and excludes both forms of
  catalogue purchases.

## Privacy

64% of suppliers are natural persons. They appear only as `supplier_key` (an HMAC
pseudonym) and never with a name (ADR-0004). A dbt test
(`assert_lp01_no_personal_identifiers`) fails the build otherwise. Public outputs should
show them as "Natural person #<first characters of the pseudonym>".

## Legitimate causes

- Local markets: in small cantons there may be one or two suppliers for many things.
  Comparing within the province helps, but a canton is smaller than a province.
- Framework agreements, maintenance of equipment by its manufacturer or authorized
  distributor, and continuity of a service.
- A supplier that is simply better or cheaper.
- Public policy: procurement rules promote purchases from the popular and solidarity
  economy (associations, cooperatives), which can concentrate awards on a few local
  organizations.

## Limitations

- CPC division (2 digits) is broad: "medical equipment" mixes very different products.
- Awards are counted, not weighted by value: many small awards count as much as one big one.
- Province, not canton, defines the local market.
- Direct awards are included: repeated direct awards to the same supplier are part of
  what this indicator looks for, but some are legally justified (e.g. sole providers).
