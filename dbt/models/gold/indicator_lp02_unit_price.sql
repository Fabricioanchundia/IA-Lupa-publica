-- LP02 "Unusually high unit price" (Lupa Pública's own indicator).
-- One row per item in a usable reference group (see price_reference_groups).
-- Methodology and limits: docs/indicators/lp02-unit-price.md
--
-- Flagged when the unit price is at least var lp02_min_ratio times the reference price
-- AND a robust outlier: robust z-score (log price vs the buyers' median, scaled by the
-- MAD) of at least var lp02_min_robust_z. `price_difference` is (price - reference) x
-- quantity: a difference against the typical price, NOT a proven overpayment.

with items as (
    select * from {{ ref('int_comparable_items') }}
),

groups as (
    select * from {{ ref('price_reference_groups') }} where usable
),

scored as (
    select
        i.ocid,
        i.award_id,
        i.item_index,
        i.buyer_id,
        i.buyer_name,
        i.buyer_region,
        i.source_month,
        i.procurement_method_details,
        i.cpc_code,
        i.unit_name,
        i.quantity,
        i.unit_price,
        g.reference_price,
        g.buyers as group_buyers,
        g.spread as group_spread,
        i.unit_price / g.reference_price as price_ratio,
        (i.log_price - g.reference_log_price) / nullif(1.4826 * g.log_mad, 0) as robust_z
    from items as i
    inner join groups as g
        on i.cpc_code = g.cpc_code and i.unit_name = g.unit_name
)

select
    *,
    price_ratio >= {{ var('lp02_min_ratio') }}
    and coalesce(robust_z >= {{ var('lp02_min_robust_z') }}, true) as flagged,
    case
        when price_ratio >= {{ var('lp02_min_ratio') }}
            and coalesce(robust_z >= {{ var('lp02_min_robust_z') }}, true)
            then round((unit_price - reference_price) * quantity, 2)
    end as price_difference
from scored
