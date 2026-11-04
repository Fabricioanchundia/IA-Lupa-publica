-- The buyer summary must add up to the process-level indicator, and rates must be
-- valid proportions. Any row returned is an error.
with totals as (
    select
        (select count(*) from {{ ref('indicator_r018_single_bid') }} where buyer_id is not null)
            as indicator_rows,
        (select count(*) from {{ ref('indicator_r018_single_bid') }}
            where buyer_id is not null and flagged) as indicator_flagged,
        (select coalesce(sum(evaluated_processes), 0) from {{ ref('buyer_r018_summary') }}) as summary_rows,
        (select coalesce(sum(single_bid_processes), 0) from {{ ref('buyer_r018_summary') }}) as summary_flagged
)

select 'totals do not match' as problem, null as buyer_id
from totals
where indicator_rows is distinct from summary_rows
   or indicator_flagged is distinct from summary_flagged

union all

select 'invalid rate', buyer_id
from {{ ref('buyer_r018_summary') }}
where single_bid_processes > evaluated_processes
   or single_bid_rate not between 0 and 1
   or expected_rate not between 0 and 1
