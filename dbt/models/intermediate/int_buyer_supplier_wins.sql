-- How many awards (and how much money) each supplier won from each buyer, by what was
-- bought (CPC division). Basis for the supplier concentration indicator (LP01).
--
-- * Catalogue purchases are excluded: in the electronic catalogue the supplier is set by
--   the catalogue, not freely chosen by the buyer. They appear in two ways: `selective`
--   without tenderers, and procedure types named "Catálogo electrónico - ..." (published
--   with method `direct`). Processes without a method are excluded too.
-- * A consortium award counts as 1/n award (and 1/n of the money) for each of its n
--   suppliers.
-- * supplier_key is a pseudonym for natural persons (ADR-0004); names only for companies.

with award_suppliers as (
    select
        ocid,
        award_id,
        supplier_key,
        supplier_type,
        supplier_name,
        count(*) over (partition by ocid, award_id) as suppliers_in_award
    from {{ ref('stg_award_suppliers') }}
    where supplier_key is not null
),

eligible_processes as (
    select
        p.ocid,
        p.buyer_id,
        p.buyer_name,
        p.source_month,
        coalesce(p.buyer_region, 'UNKNOWN') as buyer_region,
        coalesce(c.main_cpc_division, 'unknown') as cpc_division
    from {{ ref('processes') }} as p
    left join {{ ref('int_process_main_cpc') }} as c on p.ocid = c.ocid
    where p.buyer_id is not null
        and p.procurement_method is not null
        and not (p.procurement_method = 'selective' and p.number_of_tenderers is null)
        and coalesce(p.procurement_method_details, '') not ilike '%cat_logo%'
)

select
    p.buyer_id,
    arg_max(p.buyer_name, p.source_month) as buyer_name,
    arg_max(p.buyer_region, p.source_month) as buyer_region,
    p.cpc_division,
    a.supplier_key,
    any_value(a.supplier_type) as supplier_type,
    any_value(a.supplier_name) as supplier_name,
    sum(1.0 / a.suppliers_in_award) as wins,
    sum(w.award_amount / a.suppliers_in_award) as awarded_amount
from award_suppliers as a
inner join {{ ref('stg_awards') }} as w
    on a.ocid = w.ocid and a.award_id = w.award_id
inner join eligible_processes as p on a.ocid = p.ocid
group by p.buyer_id, p.cpc_division, a.supplier_key
