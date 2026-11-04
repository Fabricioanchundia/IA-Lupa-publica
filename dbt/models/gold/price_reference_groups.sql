-- Reference prices for groups of comparable items (same 9-digit CPC code and unit).
--
-- * Each BUYER counts once: first its median price in the group, then the median
--   across buyers. A buyer that buys thousands of items cannot set the reference.
-- * Prices are compared in logarithms (a price 3x higher and 3x lower are equally far).
-- * A group is usable only if buyers pay similar prices (spread = p90 / p10 of the
--   buyers' medians at most var lp02_max_spread). Otherwise the CPC code mixes
--   different products (e.g. "civil works, UNIDAD") and comparing prices is meaningless.

with buyer_medians as (
    select
        cpc_code,
        unit_name,
        buyer_id,
        count(*) as items,
        median(log_price) as buyer_log_price
    from {{ ref('int_comparable_items') }}
    group by all
)

select
    cpc_code,
    unit_name,
    sum(items) as items,
    count(*) as buyers,
    round(exp(median(buyer_log_price)), 4) as reference_price,
    median(buyer_log_price) as reference_log_price,
    mad(buyer_log_price) as log_mad,
    exp(quantile_cont(buyer_log_price, 0.9) - quantile_cont(buyer_log_price, 0.1)) as spread,
    count(*) >= {{ var('lp02_min_buyers') }}
    and sum(items) >= {{ var('lp02_min_items') }}
    and exp(quantile_cont(buyer_log_price, 0.9) - quantile_cont(buyer_log_price, 0.1))
        <= {{ var('lp02_max_spread') }} as usable
from buyer_medians
group by cpc_code, unit_name
