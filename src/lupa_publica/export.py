"""Export the PUBLIC datasets for the website (Phase 6).

Only the queries below are published, and each one lists its columns explicitly (an
allowlist): a column added to gold later is never published by accident. Natural
persons appear only as "Persona #" + the first 6 characters of their pseudonym
(ADR-0004). Before anything is written for good, every text value is scanned for
identifiers that look personal; if one is found, the export fails.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

PUBLIC_QUERIES: dict[str, str] = {
    "review_priority": """
        select buyer_id, buyer_name, buyer_region,
               r018_evaluated, r018_flagged, r018_ratio, r018_level,
               r003_evaluated, r003_flagged, r003_ratio, r003_level,
               lp01_cells_evaluated, lp01_flagged_cells, lp01_level,
               signals, review_priority
        from gold.buyer_review_priority
    """,
    "r018_buyers": """
        select buyer_id, buyer_name, buyer_region, evaluated_processes,
               single_bid_processes, single_bid_rate, expected_rate,
               observed_to_expected, p_value, q_value, significant, enough_data
        from gold.buyer_r018_summary
    """,
    "r003_buyers": """
        select buyer_id, buyer_name, buyer_region, evaluated_processes,
               short_period_processes, short_period_rate, expected_rate,
               observed_to_expected, p_value, q_value, significant, enough_data
        from gold.buyer_r003_summary
    """,
    # Written by Fabricio in Phase 6 (plus buyer_id to link to the buyer page).
    "lp01_flags": """
        select
            buyer_id,
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


def export_public(db_path: Path, out_dir: Path) -> ExportReport:
    """Write every public dataset as Parquet into ``out_dir`` (replaced atomically)."""
    staging = out_dir.with_name(out_dir.name + ".part")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    report = ExportReport()
    with duckdb.connect(str(db_path), read_only=True) as con:
        for name, query in PUBLIC_QUERIES.items():
            con.execute(f"create temp table {name} as {query}")
            problems = find_personal_identifiers(con, name)
            if problems:
                shutil.rmtree(staging, ignore_errors=True)
                raise PublicDataError(f"personal identifiers found in {', '.join(problems)}")
            target = staging / f"{name}.parquet"
            con.execute(f"copy {name} to '{target}' (format parquet)")
            # Table names come from PUBLIC_QUERIES (our own constants), never from input.
            counted = con.execute(f"select count(*) from {name}").fetchone()  # noqa: S608
            report.rows[name] = int(counted[0]) if counted else 0
    shutil.rmtree(out_dir, ignore_errors=True)
    staging.rename(out_dir)
    return report
