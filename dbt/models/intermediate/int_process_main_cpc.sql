-- What a process mainly buys: the CPC division (first 2 digits) of its most valuable item.
-- Used to compare processes with others that buy similar things (e.g. R018 baselines).
-- When no item has a price, the most frequent division is used instead.

with items as (
    select
        ocid,
        left(cpc_code, 2) as cpc_division,
        coalesce(line_amount, 0) as line_amount
    from {{ ref('stg_award_items') }}
    where cpc_code is not null
),

per_division as (
    select
        ocid,
        cpc_division,
        sum(line_amount) as division_amount,
        count(*) as division_items
    from items
    group by ocid, cpc_division
)

select
    ocid,
    arg_max(cpc_division, (division_amount, division_items)) as main_cpc_division
from per_division
group by ocid
