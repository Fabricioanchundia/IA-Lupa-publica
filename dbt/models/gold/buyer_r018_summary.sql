-- Single-bid rate per buyer, compared with what is EXPECTED for the procedures it uses.
--
-- Some procedure types have more single bids everywhere (e.g. insurance tenders), so a
-- raw rate would penalize buyers just for what they buy. The expected count adds up,
-- for each of the buyer's processes, the national single-bid rate of that procedure
-- type. observed_to_expected > 1 means more single bids than comparable processes.
-- Buyers with few processes are kept but marked `enough_data = false`.

with evaluated as (
    select * from {{ ref('indicator_r018_single_bid') }}
    where buyer_id is not null
),

baseline as (
    select
        procurement_method_details,
        avg(case when flagged then 1.0 else 0.0 end) as baseline_rate
    from evaluated
    group by procurement_method_details
),

per_buyer as (
    select
        e.buyer_id,
        arg_max(e.buyer_name, e.source_month) as buyer_name,
        arg_max(e.buyer_region, e.source_month) as buyer_region,
        count(*) as evaluated_processes,
        count(*) filter (where e.flagged) as single_bid_processes,
        sum(b.baseline_rate) as expected_single_bid
    from evaluated as e
    inner join baseline as b
        on e.procurement_method_details is not distinct from b.procurement_method_details
    group by e.buyer_id
)

select
    buyer_id,
    buyer_name,
    buyer_region,
    evaluated_processes,
    single_bid_processes,
    round(single_bid_processes / evaluated_processes, 4) as single_bid_rate,
    round(expected_single_bid / evaluated_processes, 4) as expected_rate,
    round(single_bid_processes / nullif(expected_single_bid, 0), 2) as observed_to_expected,
    evaluated_processes >= {{ var('r018_min_processes') }} as enough_data
from per_buyer
