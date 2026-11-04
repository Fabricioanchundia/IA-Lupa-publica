-- R018 "Single bid received" (Open Contracting Partnership, Cardinal).
-- One row per EVALUATED process; `flagged` is true when exactly one bid was received.
-- Methodology and limits: docs/indicators/r018-single-bid.md
--
-- A process is evaluated only if:
--   * its method is competitive (var r018_procurement_methods): direct awards have a
--     single supplier by design and would only produce false signals;
--   * it has an award, so the competition is over;
--   * SERCOP reports how many bids it received.

with processes as (
    select * from {{ ref('processes') }}
),

awarded as (
    select ocid, sum(award_amount) as awarded_amount
    from {{ ref('stg_awards') }}
    group by ocid
)

select
    p.ocid,
    p.source_month,
    p.buyer_id,
    p.buyer_name,
    p.buyer_region,
    p.procurement_method,
    p.procurement_method_details,
    p.number_of_tenderers,
    p.tender_amount,
    a.awarded_amount,
    p.number_of_tenderers = 1 as flagged
from processes as p
left join awarded as a on p.ocid = a.ocid
where p.procurement_method in (
        {%- for method in var('r018_procurement_methods') %}
        '{{ method }}'{% if not loop.last %},{% endif %}
        {%- endfor %}
    )
    and p.has_award
    and p.number_of_tenderers >= 1
