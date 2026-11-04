-- Priced items that can be compared across buyers: not bought through the electronic
-- catalogue (its prices are set by the catalogue; it also uses other CPC lengths and
-- no units), with a CPC code, a unit and a price. Basis for LP02.

select
    i.ocid,
    i.award_id,
    i.item_index,
    p.buyer_id,
    p.buyer_name,
    p.buyer_region,
    p.source_month,
    p.procurement_method_details,
    i.cpc_code,
    i.unit_name,
    i.quantity,
    i.unit_price,
    ln(i.unit_price) as log_price
from {{ ref('stg_award_items') }} as i
inner join {{ ref('processes') }} as p on i.ocid = p.ocid
where i.unit_price is not null
    and i.cpc_code is not null
    and i.unit_name is not null
    and p.buyer_id is not null
    and not (p.procurement_method = 'selective' and p.number_of_tenderers is null)
    and coalesce(p.procurement_method_details, '') not ilike '%cat_logo%'
