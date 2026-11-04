-- Single-bid rate per buyer, compared with what is EXPECTED for comparable processes.
-- Methodology: docs/indicators/r018-single-bid.md ("Comparing buyers fairly").
--
-- Expected single bids = sum over the buyer's processes of the single-bid rate of
-- comparable processes FROM OTHER BUYERS (leave-one-out: a buyer is never compared
-- with itself). "Comparable" is, from most to least specific:
--   1. same procedure type AND same CPC division (what is bought), if other buyers
--      have at least r018_min_baseline such processes;
--   2. otherwise the same procedure type;
--   3. otherwise all evaluated processes.

with evaluated as (
    select
        buyer_id,
        buyer_name,
        buyer_region,
        source_month,
        procurement_method_details as procedure_type,
        coalesce(main_cpc_division, 'unknown') as cpc_division,
        case when flagged then 1 else 0 end as is_single
    from {{ ref('indicator_r018_single_bid') }}
    where buyer_id is not null
),

-- Counts per buyer and cell (procedure type x CPC division).
buyer_cell as (
    select
        buyer_id,
        procedure_type,
        cpc_division,
        count(*) as n,
        sum(is_single) as single
    from evaluated
    group by all
),

cell_totals as (
    select procedure_type, cpc_division, sum(n) as n, sum(single) as single
    from buyer_cell
    group by all
),

type_totals as (
    select procedure_type, sum(n) as n, sum(single) as single
    from buyer_cell
    group by all
),

overall as (
    select sum(n) as n, sum(single) as single from buyer_cell
),

buyer_type as (
    select buyer_id, procedure_type, sum(n) as n, sum(single) as single
    from buyer_cell
    group by all
),

buyer_total as (
    select buyer_id, sum(n) as n, sum(single) as single
    from buyer_cell
    group by all
),

-- Leave-one-out baselines for each buyer cell.
baselines as (
    select
        bc.buyer_id,
        bc.procedure_type,
        bc.cpc_division,
        bc.n,
        bc.single,
        ct.n - bc.n as cell_others_n,
        (ct.single - bc.single) / nullif(ct.n - bc.n, 0) as cell_rate,
        tt.n - bt.n as type_others_n,
        (tt.single - bt.single) / nullif(tt.n - bt.n, 0) as type_rate,
        (o.single - btot.single) / nullif(o.n - btot.n, 0) as overall_rate
    from buyer_cell as bc
    inner join cell_totals as ct
        on bc.procedure_type is not distinct from ct.procedure_type
        and bc.cpc_division = ct.cpc_division
    inner join type_totals as tt
        on bc.procedure_type is not distinct from tt.procedure_type
    inner join buyer_type as bt
        on bc.buyer_id = bt.buyer_id
        and bc.procedure_type is not distinct from bt.procedure_type
    inner join buyer_total as btot on bc.buyer_id = btot.buyer_id
    cross join overall as o
),

expected as (
    select
        buyer_id,
        n,
        single,
        case
            when cell_others_n >= {{ var('r018_min_baseline') }} then n * cell_rate
            when type_others_n >= {{ var('r018_min_baseline') }} then n * type_rate
            else n * coalesce(overall_rate, 0)
        end as expected_single,
        -- The simpler baseline (procedure type only), kept to show what CPC changes.
        case
            when type_others_n >= {{ var('r018_min_baseline') }} then n * type_rate
            else n * coalesce(overall_rate, 0)
        end as expected_single_by_type,
        cell_others_n >= {{ var('r018_min_baseline') }} as used_cpc_baseline
    from baselines
),

per_buyer as (
    select
        buyer_id,
        cast(sum(n) as bigint) as evaluated_processes,
        cast(sum(single) as bigint) as single_bid_processes,
        sum(expected_single) as expected_single_bid,
        sum(expected_single_by_type) as expected_single_bid_by_type,
        sum(case when used_cpc_baseline then n else 0 end) as processes_with_cpc_baseline
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
),

scored as (
    select
        p.buyer_id,
        nm.buyer_name,
        nm.buyer_region,
        p.evaluated_processes,
        p.single_bid_processes,
        round(p.single_bid_processes / p.evaluated_processes, 4) as single_bid_rate,
        round(p.expected_single_bid / p.evaluated_processes, 4) as expected_rate,
        round(p.single_bid_processes / nullif(p.expected_single_bid, 0), 2) as observed_to_expected,
        round(p.single_bid_processes / nullif(p.expected_single_bid_by_type, 0), 2)
            as observed_to_expected_by_type,
        round(p.processes_with_cpc_baseline / p.evaluated_processes, 4) as cpc_baseline_share,
        {{ poisson_upper_tail('p.single_bid_processes', 'p.expected_single_bid') }} as p_value,
        p.evaluated_processes >= {{ var('r018_min_processes') }} as enough_data
    from per_buyer as p
    inner join names as nm on p.buyer_id = nm.buyer_id
),

tested as (
    {{ benjamini_hochberg('scored', 'p_value', 'enough_data', 'buyer_id') }}
)

select
    * exclude (p_value, q_value),
    round(p_value, 6) as p_value,
    round(q_value, 6) as q_value,
    coalesce(
        q_value < {{ var('fdr_alpha') }}
        and single_bid_processes >= {{ var('min_flagged_for_significance') }},
        false
    ) as significant
from tested
