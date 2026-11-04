-- LP01 "Unusual supplier concentration" (Lupa Pública's own indicator; Cardinal has
-- no equivalent). One row per buyer and CPC division with enough awards.
-- Methodology and limits: docs/indicators/lp01-supplier-concentration.md
--
-- Question: is this buyer's top supplier winning more of its awards than expected?
-- "Expected" is the HIGHER of two references, both from OTHER buyers (leave-one-out):
-- * how concentrated buyers usually are for this kind of purchase (median top-supplier
--   share in the same CPC division): some categories, like local food services, are
--   concentrated everywhere;
-- * how often this supplier wins from comparable buyers in the province: a market
--   leader or sole provider wins a lot everywhere.
-- Only a buyer above both references, beyond chance, is flagged.

with wins as (
    select * from {{ ref('int_buyer_supplier_wins') }}
),

cells as (
    select
        buyer_id,
        any_value(buyer_name) as buyer_name,
        any_value(buyer_region) as buyer_region,
        cpc_division,
        sum(wins) as cell_awards,
        count(*) as cell_suppliers,
        sum(awarded_amount) as cell_amount
    from wins
    group by buyer_id, cpc_division
),

top_supplier as (
    select * exclude (rn)
    from (
        select
            buyer_id,
            cpc_division,
            supplier_key,
            supplier_type,
            supplier_name,
            wins as top_wins,
            awarded_amount as top_amount,
            row_number() over (
                partition by buyer_id, cpc_division order by wins desc, supplier_key
            ) as rn
        from wins
    )
    where rn = 1
),

-- Market of comparable buyers: same province and CPC division, and nationwide.
region_market as (
    select buyer_region, cpc_division, sum(wins) as awards
    from wins group by all
),

region_supplier as (
    select buyer_region, cpc_division, supplier_key, sum(wins) as wins
    from wins group by all
),

national_market as (
    select cpc_division, sum(wins) as awards
    from wins group by all
),

national_supplier as (
    select cpc_division, supplier_key, sum(wins) as wins
    from wins group by all
),

scored as (
    select
        c.buyer_id,
        c.buyer_name,
        c.buyer_region,
        c.cpc_division,
        c.cell_awards,
        c.cell_suppliers,
        c.cell_amount,
        t.supplier_key,
        t.supplier_type,
        t.supplier_name,
        t.top_wins,
        t.top_amount,
        t.top_wins / c.cell_awards as top_share,
        -- Leave-one-out: the market without this buyer. Province first, else nationwide.
        rm.awards - c.cell_awards as region_others_awards,
        case
            when rm.awards - c.cell_awards >= {{ var('lp01_min_baseline') }}
                then (coalesce(rs.wins, 0) - t.top_wins + 0.5) / (rm.awards - c.cell_awards + 1)
            else (coalesce(ns.wins, 0) - t.top_wins + 0.5) / (nm.awards - c.cell_awards + 1)
        end as supplier_share_elsewhere,
        rm.awards - c.cell_awards >= {{ var('lp01_min_baseline') }} as compared_in_province
    from cells as c
    inner join top_supplier as t
        on c.buyer_id = t.buyer_id and c.cpc_division = t.cpc_division
    inner join region_market as rm
        on c.buyer_region = rm.buyer_region and c.cpc_division = rm.cpc_division
    left join region_supplier as rs
        on c.buyer_region = rs.buyer_region
        and c.cpc_division = rs.cpc_division
        and t.supplier_key = rs.supplier_key
    inner join national_market as nm on c.cpc_division = nm.cpc_division
    left join national_supplier as ns
        on c.cpc_division = ns.cpc_division and t.supplier_key = ns.supplier_key
    where c.cell_awards >= {{ var('lp01_min_awards') }}
),

-- Typical concentration of OTHER buyers' cells in the same CPC division.
peers as (
    select
        a.buyer_id,
        a.cpc_division,
        count(b.buyer_id) as peer_cells,
        median(b.top_share) as peer_median_top_share
    from scored as a
    left join scored as b
        on a.cpc_division = b.cpc_division and a.buyer_id <> b.buyer_id
    group by a.buyer_id, a.cpc_division
),

overall as (
    select median(top_share) as overall_median_top_share from scored
),

with_p as (
    select
        s.*,
        case
            when pe.peer_cells >= {{ var('lp01_min_peer_cells') }} then pe.peer_median_top_share
            else o.overall_median_top_share
        end as typical_top_share,
        pe.peer_cells,
        s.cell_awards * greatest(
            case
                when pe.peer_cells >= {{ var('lp01_min_peer_cells') }}
                    then pe.peer_median_top_share
                else o.overall_median_top_share
            end,
            s.supplier_share_elsewhere
        ) as expected_top_wins,
        true as eligible
    from scored as s
    inner join peers as pe
        on s.buyer_id = pe.buyer_id and s.cpc_division = pe.cpc_division
    cross join overall as o
),

with_pvalue as (
    select
        *,
        {{ poisson_upper_tail('floor(top_wins)', 'expected_top_wins') }} as p_value
    from with_p
),

tested as (
    {{ benjamini_hochberg('with_pvalue', 'p_value', 'eligible', "buyer_id || cpc_division") }}
)

select
    buyer_id,
    buyer_name,
    buyer_region,
    cpc_division,
    round(cell_awards, 2) as cell_awards,
    cell_suppliers,
    round(cell_amount, 2) as cell_amount,
    supplier_key,
    supplier_type,
    -- Names only for companies and public entities (ADR-0004).
    case when supplier_type in ('private_company', 'public_entity') then supplier_name end
        as supplier_name,
    round(top_wins, 2) as top_wins,
    round(top_amount, 2) as top_amount,
    round(top_share, 4) as top_share,
    round(supplier_share_elsewhere, 4) as supplier_share_elsewhere,
    round(typical_top_share, 4) as typical_top_share,
    peer_cells,
    round(expected_top_wins, 2) as expected_top_wins,
    compared_in_province,
    round(p_value, 6) as p_value,
    round(q_value, 6) as q_value,
    coalesce(
        q_value < {{ var('fdr_alpha') }}
        and top_share >= {{ var('lp01_min_top_share') }}
        and top_wins >= {{ var('min_flagged_for_significance') }},
        false
    ) as flagged
from tested
