-- Monitors our reading of SERCOP's durationInDays: complete 24-hour periods between
-- tender start and end. A warning (not an error) if SERCOP ever publishes otherwise.
{{ config(severity='warn') }}

select ocid, tender_duration_days, tender_period_start, tender_period_end
from {{ ref('processes') }}
where tender_duration_days is not null
  and tender_period_end > tender_period_start
  and tender_duration_days
      <> floor((epoch(tender_period_end) - epoch(tender_period_start)) / 86400)
