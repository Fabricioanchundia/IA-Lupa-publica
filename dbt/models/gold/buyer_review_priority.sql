-- One row per buyer: the public indicators side by side and a review priority.
-- This is a PRIORITY FOR REVIEW, not a risk score or a judgement: it says where a
-- journalist or auditor could look first, and why. Methodology: docs/indicators/README.md
--
-- Per indicator (R018, R003): 'high' = significant and >= 2x expected, 'medium' =
-- significant and >= 1.5x, 'low' = significant but a small excess, 'none', or
-- 'insufficient_data'. LP01: 'signal' when at least one CPC division is flagged.
-- LP02 is experimental and not included.

with r018 as (
    select
        buyer_id,
        buyer_name,
        buyer_region,
        evaluated_processes as r018_evaluated,
        single_bid_processes as r018_flagged,
        observed_to_expected as r018_ratio,
        {{ signal_level('enough_data', 'significant', 'observed_to_expected') }} as r018_level
    from {{ ref('buyer_r018_summary') }}
),

r003 as (
    select
        buyer_id,
        buyer_name,
        buyer_region,
        evaluated_processes as r003_evaluated,
        short_period_processes as r003_flagged,
        observed_to_expected as r003_ratio,
        {{ signal_level('enough_data', 'significant', 'observed_to_expected') }} as r003_level
    from {{ ref('buyer_r003_summary') }}
),

lp01 as (
    select
        buyer_id,
        any_value(buyer_name) as buyer_name,
        any_value(buyer_region) as buyer_region,
        count(*) as lp01_cells_evaluated,
        count(*) filter (where flagged) as lp01_flagged_cells,
        max(top_share) filter (where flagged) as lp01_max_top_share
    from {{ ref('indicator_lp01_supplier_concentration') }}
    group by buyer_id
),

buyers as (
    select buyer_id, any_value(buyer_name) as buyer_name, any_value(buyer_region) as buyer_region
    from (
        select buyer_id, buyer_name, buyer_region from r018
        union all
        select buyer_id, buyer_name, buyer_region from r003
        union all
        select buyer_id, buyer_name, buyer_region from lp01
    )
    group by buyer_id
),

combined as (
    select
        b.buyer_id,
        b.buyer_name,
        b.buyer_region,
        r018.r018_evaluated,
        r018.r018_flagged,
        r018.r018_ratio,
        coalesce(r018.r018_level, 'insufficient_data') as r018_level,
        r003.r003_evaluated,
        r003.r003_flagged,
        r003.r003_ratio,
        coalesce(r003.r003_level, 'insufficient_data') as r003_level,
        lp01.lp01_cells_evaluated,
        lp01.lp01_flagged_cells,
        lp01.lp01_max_top_share,
        case
            when lp01.buyer_id is null then 'insufficient_data'
            when lp01.lp01_flagged_cells > 0 then 'signal'
            else 'none'
        end as lp01_level
    from buyers as b
    left join r018 on b.buyer_id = r018.buyer_id
    left join r003 on b.buyer_id = r003.buyer_id
    left join lp01 on b.buyer_id = lp01.buyer_id
)

select
    *,
    (r018_level in ('high', 'medium'))::int
    + (r003_level in ('high', 'medium'))::int
    + (lp01_level = 'signal')::int as signals,
    case
        when (r018_level in ('high', 'medium'))::int
            + (r003_level in ('high', 'medium'))::int
            + (lp01_level = 'signal')::int >= 2
            or 'high' in (r018_level, r003_level)
            then 'review_first'
        when (r018_level in ('high', 'medium'))::int
            + (r003_level in ('high', 'medium'))::int
            + (lp01_level = 'signal')::int = 1
            then 'review'
        when r018_level = 'insufficient_data'
            and r003_level = 'insufficient_data'
            and lp01_level = 'insufficient_data'
            then 'insufficient_data'
        else 'no_signal'
    end as review_priority
from combined
