-- R003 "Short submission period" (Open Contracting Partnership, Cardinal).
-- One row per EVALUATED process; `flagged` when bidders had unusually few days.
-- Methodology and limits: docs/indicators/r003-short-period.md
--
-- * Days are COMPLETE 24-hour periods between tender start and end: the same
--   definition SERCOP uses for durationInDays (most processes open in the afternoon
--   and close in the morning, so counting calendar dates adds a day).
-- * "Short" is relative to the same procedure type: below its 5th percentile
--   (var r003_percentile), because each type has different legal minimums and we
--   have not loaded those minimums with their legal citations yet.

with periods as (
    select
        ocid,
        source_month,
        buyer_id,
        buyer_name,
        buyer_region,
        procurement_method,
        procurement_method_details,
        tender_period_start,
        tender_period_end,
        cast(
            floor((epoch(tender_period_end) - epoch(tender_period_start)) / 86400) as integer
        ) as tender_days
    from {{ ref('processes') }}
    where procurement_method in (
            {%- for method in var('r003_procurement_methods') %}
            '{{ method }}'{% if not loop.last %},{% endif %}
            {%- endfor %}
        )
        and tender_period_start is not null
        and tender_period_end > tender_period_start
),

thresholds as (
    select
        procurement_method_details,
        count(*) as group_processes,
        quantile_disc(tender_days, {{ var('r003_percentile') }}) as threshold_days,
        median(tender_days) as group_median_days
    from periods
    group by procurement_method_details
)

select
    p.*,
    t.threshold_days,
    t.group_median_days,
    t.group_processes,
    p.tender_days < t.threshold_days as flagged
from periods as p
inner join thresholds as t
    on p.procurement_method_details is not distinct from t.procurement_method_details
where t.group_processes >= {{ var('r003_min_group') }}
