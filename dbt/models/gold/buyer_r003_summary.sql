-- Short-submission-period rate per buyer, compared with what is EXPECTED for the
-- procedure types it uses. Leave-one-out: the expected rate of each procedure type
-- comes from OTHER buyers (same rule as buyer_r018_summary).

with evaluated as (
    select
        buyer_id,
        buyer_name,
        buyer_region,
        source_month,
        procurement_method_details as procedure_type,
        case when flagged then 1 else 0 end as is_short
    from {{ ref('indicator_r003_short_period') }}
    where buyer_id is not null
),

buyer_type as (
    select buyer_id, procedure_type, count(*) as n, sum(is_short) as short
    from evaluated
    group by all
),

type_totals as (
    select procedure_type, sum(n) as n, sum(short) as short
    from buyer_type
    group by all
),

expected as (
    select
        bt.buyer_id,
        bt.n,
        bt.short,
        bt.n * coalesce((tt.short - bt.short) / nullif(tt.n - bt.n, 0), 0) as expected_short
    from buyer_type as bt
    inner join type_totals as tt
        on bt.procedure_type is not distinct from tt.procedure_type
),

per_buyer as (
    select
        buyer_id,
        cast(sum(n) as bigint) as evaluated_processes,
        cast(sum(short) as bigint) as short_period_processes,
        sum(expected_short) as expected_short
    from expected
    group by buyer_id
),

names as (
    select
        buyer_id,
        arg_max(buyer_name, source_month) as buyer_name,
        arg_max(buyer_region, source_month) as buyer_region
    from evaluated
    group by buyer_id
)

select
    p.buyer_id,
    nm.buyer_name,
    nm.buyer_region,
    p.evaluated_processes,
    p.short_period_processes,
    round(p.short_period_processes / p.evaluated_processes, 4) as short_period_rate,
    round(p.expected_short / p.evaluated_processes, 4) as expected_rate,
    round(p.short_period_processes / nullif(p.expected_short, 0), 2) as observed_to_expected,
    p.evaluated_processes >= {{ var('r003_min_processes') }} as enough_data
from per_buyer as p
inner join names as nm on p.buyer_id = nm.buyer_id
