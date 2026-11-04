"""Export the PUBLIC datasets for the website (Phase 6).

Only the queries below are published, and each one lists its columns explicitly (an
allowlist): a column added to gold later is never published by accident. Natural
persons appear only as "Persona #" + the first 6 characters of their pseudonym
(ADR-0004); buyers registered with a person's number get an opaque id. Free-text
titles have anything that looks like a cédula or a person's RUC replaced. Before
anything is written for good, every text value is scanned for identifiers that look
personal; if one is found, the export fails.

Files are gzipped CSV: the website reads them with DuckDB-WASM's core engine, without
downloading extensions from third parties (ADR-0005).
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from lupa_publica.cpc import CPC_DIVISIONS
from lupa_publica.privacy import KEY_ENV, MissingKeyError, load_key, pseudonymize

PUBLIC_QUERIES: dict[str, str] = {
    # In titles, anything that looks like a cédula (10 digits) or a person's RUC (13 digits),
    # i.e. third digit 0-5, is replaced. RE2 has no look-behind, so boundaries are captured.
    "processes": """
        with awarded as (
            select ocid, sum(award_amount) as awarded_amount
            from silver.stg_awards group by ocid
        ),
        main_supplier as (
            select s.ocid, arg_max(
                case
                    when s.supplier_type in ('private_company', 'public_entity')
                        then s.supplier_name
                    when s.supplier_type = 'natural_person'
                        then 'Persona #' || left(s.supplier_key, 6)
                    else 'Proveedor #' || left(s.supplier_key, 6)
                end,
                coalesce(w.award_amount, 0)
            ) as supplier_label
            from silver.stg_award_suppliers as s
            join silver.stg_awards as w on s.ocid = w.ocid and s.award_id = w.award_id
            where s.supplier_key is not null
            group by s.ocid
        )
        select
            p.ocid,
            p.source_month as month,
            public_buyer_id(p.buyer_id) as buyer_id,
            p.procurement_method as method,
            p.procurement_method_details as procedure,
            regexp_replace(
                coalesce(p.tender_title, ''),
                '(^|[^0-9])[0-9]{2}[0-5][0-9]{7}([0-9]{3})?([^0-9]|$)',
                '\\1[identificación oculta]\\3',
                'g'
            ) as title,
            coalesce(a.awarded_amount, p.tender_amount) as amount,
            p.number_of_tenderers as tenderers,
            coalesce(r18.flagged, false) as single_bid,
            coalesce(r3.flagged, false) as short_period,
            c.main_cpc_division as cpc_division,
            ms.supplier_label
        from silver.processes as p
        left join awarded as a on p.ocid = a.ocid
        left join gold.indicator_r018_single_bid as r18 on p.ocid = r18.ocid
        left join gold.indicator_r003_short_period as r3 on p.ocid = r3.ocid
        left join silver.int_process_main_cpc as c on p.ocid = c.ocid
        left join main_supplier as ms on p.ocid = ms.ocid
    """,
    "buyers": """
        select public_buyer_id(buyer_id) as buyer_id,
               arg_max(buyer_name, source_month) as buyer_name,
               arg_max(buyer_region, source_month) as buyer_region
        from silver.processes
        where buyer_id is not null
        group by buyer_id
    """,
    "cpc_divisions": "select code as cpc_division, name from cpc_names",
    "review_priority": """
        select public_buyer_id(buyer_id) as buyer_id, buyer_name, buyer_region,
               r018_evaluated, r018_flagged, r018_ratio, r018_level,
               r003_evaluated, r003_flagged, r003_ratio, r003_level,
               lp01_cells_evaluated, lp01_flagged_cells, lp01_level,
               signals, review_priority
        from gold.buyer_review_priority
    """,
    "r018_buyers": """
        select public_buyer_id(buyer_id) as buyer_id, buyer_name, buyer_region,
               evaluated_processes, single_bid_processes, single_bid_rate, expected_rate,
               observed_to_expected, p_value, q_value, significant, enough_data
        from gold.buyer_r018_summary
    """,
    "r003_buyers": """
        select public_buyer_id(buyer_id) as buyer_id, buyer_name, buyer_region,
               evaluated_processes, short_period_processes, short_period_rate, expected_rate,
               observed_to_expected, p_value, q_value, significant, enough_data
        from gold.buyer_r003_summary
    """,
    # Written by Fabricio in Phase 6 (plus buyer_id to link to the buyer page).
    "lp01_flags": """
        select
            public_buyer_id(buyer_id) as buyer_id,
            buyer_name,
            buyer_region,
            cpc_division,
            cell_awards,
            top_share,
            typical_top_share,
            case
                when supplier_type in ('private_company', 'public_entity') then supplier_name
                else 'Persona #' || left(supplier_key, 6)
            end as supplier_label,
            q_value
        from gold.indicator_lp01_supplier_concentration
        where flagged
    """,
    "monthly_coverage": """
        select source_month,
               count(*) as processes,
               count(*) filter (where procurement_method in ('open', 'selective', 'limited'))
                   as competitive_processes,
               count(*) filter (where has_award) as awarded_processes,
               count(buyer_region) as with_province
        from silver.processes
        group by source_month
    """,
}

# 13 digits whose third digit is 0-5: the RUC (or cédula + 001) of a natural person.
PERSON_RUC = re.compile(r"(?<!\d)\d{2}[0-5]\d{10}(?!\d)")
# A cédula (10 digits) or a person's RUC (13 digits) inside an identifier.
PERSON_ID = re.compile(r"(?<!\d)\d{2}[0-5]\d{7}(?:\d{3})?(?!\d)")
BUYER_PREFIX = "entidad-"
BUYER_PSEUDONYM_CHARS = 12
# A full HMAC pseudonym (64 hex characters): only its first 6 may be published.
FULL_PSEUDONYM = re.compile(r"[0-9a-f]{64}")


class PublicDataError(RuntimeError):
    """A public dataset contains something that looks like personal data."""


@dataclass
class ExportReport:
    rows: dict[str, int] = field(default_factory=dict)


def find_personal_identifiers(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Text values in ``table`` that look like a person's RUC or a full pseudonym."""
    text_columns = [
        name
        for name, dtype, *_ in con.execute(f"describe {table}").fetchall()  # noqa: S608
        if str(dtype).upper().startswith("VARCHAR")
    ]
    problems: list[str] = []
    for column in text_columns:
        values = con.execute(
            f'select distinct "{column}" from {table} where "{column}" is not null'  # noqa: S608
        ).fetchall()
        for (value,) in values:
            if PERSON_RUC.search(value) or FULL_PSEUDONYM.search(value):
                problems.append(f"{table}.{column}")
                break
    return problems


def buyer_id_publisher() -> Callable[[str], str]:
    """Maps a buyer id to the id we publish.

    Public entities keep their SERCOP id (it is public and keeps links stable). A few
    buyers are registered with a PERSON's number, e.g. a notary office uses the notary's
    own RUC: those get an opaque, stable id from the same keyed hash as ADR-0004, so the
    cédula is never published. The key is only needed if such a buyer exists.
    """
    key: list[bytes] = []

    def publish(buyer_id: str) -> str:
        if not PERSON_ID.search(buyer_id):
            return buyer_id
        if not key:
            key.append(load_key())
        return BUYER_PREFIX + pseudonymize(buyer_id, key[0])[:BUYER_PSEUDONYM_CHARS]

    return publish


def export_public(db_path: Path, out_dir: Path) -> ExportReport:
    """Write every public dataset as gzipped CSV into ``out_dir`` (replaced atomically)."""
    staging = out_dir.with_name(out_dir.name + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    report = ExportReport()
    with duckdb.connect(str(db_path), read_only=True) as con:
        con.execute("create temp table cpc_names (code varchar, name varchar)")
        con.executemany("insert into cpc_names values (?, ?)", list(CPC_DIVISIONS.items()))
        con.create_function("public_buyer_id", buyer_id_publisher(), ["VARCHAR"], "VARCHAR")
        for name, query in PUBLIC_QUERIES.items():
            try:
                con.execute(f"create temp table {name} as {query}")
            except duckdb.InvalidInputException as exc:
                # DuckDB wraps errors raised inside our Python function; show the real one.
                if MissingKeyError.__name__ in str(exc):
                    shutil.rmtree(staging, ignore_errors=True)
                    raise MissingKeyError(
                        f"{KEY_ENV} is needed to hide a buyer id. Load it first: "
                        "set -a && source .env && set +a"
                    ) from exc
                raise
            problems = find_personal_identifiers(con, name)
            if problems:
                shutil.rmtree(staging, ignore_errors=True)
                raise PublicDataError(f"personal identifiers found in {', '.join(problems)}")
            target = staging / f"{name}.csv.gz"
            con.execute(f"copy {name} to '{target}' (format csv, header, compression gzip)")
            # Table names come from PUBLIC_QUERIES (our own constants), never from input.
            counted = con.execute(f"select count(*) from {name}").fetchone()  # noqa: S608
            report.rows[name] = int(counted[0]) if counted else 0
    shutil.rmtree(out_dir, ignore_errors=True)
    staging.rename(out_dir)
    return report
