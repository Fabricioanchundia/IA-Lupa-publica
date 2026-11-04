-- Privacy guard for LP01 (ADR-0004): a top supplier that is a natural person (or
-- could be) must appear only by pseudonym, never by name or raw identifier.
select buyer_id, cpc_division, supplier_type
from {{ ref('indicator_lp01_supplier_concentration') }}
where supplier_type not in ('private_company', 'public_entity')
  and (
      supplier_name is not null
      or not regexp_full_match(supplier_key, '^[0-9a-f]{64}$')
  )
