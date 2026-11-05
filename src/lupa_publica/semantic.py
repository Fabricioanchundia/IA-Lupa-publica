"""What each public table and column means, written for the language model.

The model never sees the data itself before answering, only this description (plus a
few real example values), so a good description is what makes the SQL right. Every
column the public export writes must be described here; a test enforces it, so a new
column cannot reach the AI without an explanation.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class TableDoc:
    description: str
    columns: dict[str, str]


TABLES: dict[str, TableDoc] = {
    "processes": TableDoc(
        "One row per public procurement process published by SERCOP (Ecuador).",
        {
            "ocid": "unique process id (Open Contracting)",
            "month": "month the process was published, text 'YYYY-MM' (e.g. '2025-03')",
            "buyer_id": "public entity that buys; join buyers.buyer_id",
            "method": "OCDS method: 'open', 'selective', 'limited' or 'direct'",
            "procedure": "SERCOP procedure name, free text (use ILIKE); see known values",
            "title": "process title; usually only a code like 'Orden de compra CE-...'",
            "amount": "amount in US dollars (awarded, or budgeted if not awarded yet)",
            "tenderers": "number of bids received; NULL when not reported",
            "single_bid": "true when a competitive process received only one bid (signal R018)",
            "short_period": "true when the bidding period was unusually short (signal R003)",
            "cpc_division": "two-digit product category code; join cpc_divisions",
            "supplier_label": (
                "main supplier: company name in capitals, or 'Persona #xxxxxx' for an "
                "anonymous natural person (never try to identify them)"
            ),
        },
    ),
    "buyers": TableDoc(
        "Public entities (municipalities, hospitals, ministries...).",
        {
            "buyer_id": "entity id",
            "buyer_name": "official name in CAPITALS; search it with ILIKE",
            "buyer_region": "province in CAPITALS without accents (see known values)",
        },
    ),
    "cpc_divisions": TableDoc(
        "Names of the product categories (UN CPC divisions), in Spanish.",
        {
            "cpc_division": "two-digit code, text (e.g. '53')",
            "name": "category name in Spanish, e.g. 'Obras de construcción'",
        },
    ),
    "review_priority": TableDoc(
        "One row per entity: how its risk signals compare with similar entities. "
        "This is the ONLY table with signal levels (r018_level, r003_level, lp01_level) "
        "and review_priority.",
        {
            "buyer_id": "entity id",
            "buyer_name": "entity name in CAPITALS",
            "buyer_region": "province in CAPITALS without accents",
            "r018_evaluated": "competitive processes evaluated for single bid",
            "r018_flagged": "of those, processes with a single bid",
            "r018_ratio": "single-bid rate divided by the expected rate (2 = twice as usual)",
            "r018_level": "'high', 'medium', 'low', 'none' or 'insufficient_data'",
            "r003_evaluated": "processes evaluated for short bidding period",
            "r003_flagged": "of those, processes with a short period",
            "r003_ratio": "short-period rate divided by the expected rate",
            "r003_level": "'high', 'medium', 'low', 'none' or 'insufficient_data'",
            "lp01_cells_evaluated": "categories evaluated for supplier concentration",
            "lp01_flagged_cells": "categories where one supplier wins unusually often",
            "lp01_level": "'signal', 'none' or 'insufficient_data'",
            "signals": "number of clear signals, 0 to 3",
            "review_priority": "'review_first', 'review', 'no_signal' or 'insufficient_data'",
        },
    ),
    "r018_buyers": TableDoc(
        "Single-bid signal (R018) per entity, with its statistics. It has NO level column: "
        "for 'high'/'medium' levels use review_priority.r018_level.",
        {
            "buyer_id": "entity id",
            "buyer_name": "entity name in CAPITALS",
            "buyer_region": "province in CAPITALS without accents",
            "evaluated_processes": "competitive processes evaluated",
            "single_bid_processes": "processes with only one bid",
            "single_bid_rate": "share with one bid, 0 to 1",
            "expected_rate": "share expected for similar purchases, 0 to 1",
            "observed_to_expected": "single_bid_rate / expected_rate",
            "p_value": "probability of seeing this many by chance",
            "q_value": "p_value corrected for many comparisons",
            "significant": "true when the excess is unlikely to be chance",
            "enough_data": "true when there are enough processes to judge",
        },
    ),
    "r003_buyers": TableDoc(
        "Short bidding period signal (R003) per entity, with its statistics. It has NO level "
        "column: for 'high'/'medium' levels use review_priority.r003_level.",
        {
            "buyer_id": "entity id",
            "buyer_name": "entity name in CAPITALS",
            "buyer_region": "province in CAPITALS without accents",
            "evaluated_processes": "processes evaluated",
            "short_period_processes": "processes with an unusually short period",
            "short_period_rate": "share with a short period, 0 to 1",
            "expected_rate": "share expected for similar purchases, 0 to 1",
            "observed_to_expected": "short_period_rate / expected_rate",
            "p_value": "probability of seeing this many by chance",
            "q_value": "p_value corrected for many comparisons",
            "significant": "true when the excess is unlikely to be chance",
            "enough_data": "true when there are enough processes to judge",
        },
    ),
    "lp01_flags": TableDoc(
        "Entity + category pairs where one supplier wins an unusual share of contracts.",
        {
            "buyer_id": "entity id",
            "buyer_name": "entity name in CAPITALS",
            "buyer_region": "province in CAPITALS without accents",
            "cpc_division": "category code; join cpc_divisions",
            "cell_awards": "contracts awarded by this entity in this category",
            "top_share": "share won by the top supplier, 0 to 1",
            "typical_top_share": "top supplier share that is typical elsewhere, 0 to 1",
            "supplier_label": "top supplier: company name or 'Persona #xxxxxx'",
            "q_value": "corrected probability that the concentration is chance",
        },
    ),
    "monthly_coverage": TableDoc(
        "Processes published per month.",
        {
            "source_month": "month, text 'YYYY-MM'",
            "processes": "processes published that month",
            "competitive_processes": "of those, open/selective/limited processes",
            "awarded_processes": "of those, processes with an award",
            "with_province": "of those, processes whose entity has a known province",
        },
    ),
}


def undocumented_columns(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Columns present in the loaded tables that TABLES does not describe."""
    missing: list[str] = []
    for table, doc in TABLES.items():
        for (column,) in con.execute(
            "select column_name from information_schema.columns where table_name = ? "
            "order by ordinal_position",
            [table],
        ).fetchall():
            if column not in doc.columns:
                missing.append(f"{table}.{column}")
    return missing


def known_values(con: duckdb.DuckDBPyConnection) -> dict[str, list[str]]:
    """A few real values that help the model write exact filters."""
    provinces = con.execute(
        "select distinct buyer_region from buyers where buyer_region is not null order by 1"
    ).fetchall()
    procedures = con.execute(
        "select procedure from processes where procedure is not null "
        "group by 1 order by count(*) desc limit 12"
    ).fetchall()
    months = con.execute("select min(month), max(month) from processes").fetchone()
    return {
        "buyers.buyer_region": [str(row[0]) for row in provinces],
        "processes.procedure (most common)": [str(row[0])[:80] for row in procedures],
        "processes.month (first, last)": [str(m) for m in (months or ()) if m is not None],
    }


def describe_schema(con: duckdb.DuckDBPyConnection) -> str:
    """The schema text given to the model."""
    lines: list[str] = []
    for table, doc in TABLES.items():
        lines.append(f"TABLE {table} -- {doc.description}")
        for column, meaning in doc.columns.items():
            lines.append(f"  {column}: {meaning}")
        lines.append("")
    lines.append("KNOWN VALUES")
    for label, values in known_values(con).items():
        lines.append(f"  {label}: " + ", ".join(f"'{v}'" for v in values))
    return "\n".join(lines)
