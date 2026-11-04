from pathlib import Path

import duckdb
import pytest

from lupa_publica.export import PUBLIC_QUERIES, PublicDataError, export_public

PERSON_KEY = "46249a" + "b" * 58  # a full 64-character pseudonym


def make_gold(db_path: Path, *, lp01_name: str = "RAGA S.A.S.") -> None:
    """A tiny database with the tables the public queries read."""
    with duckdb.connect(str(db_path)) as con:
        con.execute("create schema gold")
        con.execute("create schema silver")
        con.execute("""
            create table gold.buyer_review_priority as select
                'EC-RUC-1760001550001' as buyer_id, 'GAD X' as buyer_name, 'MANABI' as buyer_region,
                30 as r018_evaluated, 12 as r018_flagged, 2.5 as r018_ratio, 'high' as r018_level,
                null::int as r003_evaluated, null::int as r003_flagged, null::double as r003_ratio,
                'insufficient_data' as r003_level, 3 as lp01_cells_evaluated,
                1 as lp01_flagged_cells, 'signal' as lp01_level, 2 as signals,
                'review_first' as review_priority, 'secret' as column_added_later
        """)
        for table, flagged_col in [
            ("buyer_r018_summary", "single_bid_processes"),
            ("buyer_r003_summary", "short_period_processes"),
        ]:
            rate_col = "single_bid_rate" if "r018" in table else "short_period_rate"
            con.execute(f"""
                create table gold.{table} as select
                    'EC-RUC-1760001550001' as buyer_id, 'GAD X' as buyer_name,
                    'MANABI' as buyer_region, 30 as evaluated_processes, 12 as {flagged_col},
                    0.4 as {rate_col}, 0.16 as expected_rate, 2.5 as observed_to_expected,
                    0.001 as p_value, 0.01 as q_value, true as significant, true as enough_data
            """)
        con.execute(
            """
            create table gold.indicator_lp01_supplier_concentration as
            select * from (values
                ('EC-RUC-1760001550001', 'GAD X', 'MANABI', '43', 10.0, 1.0, 0.3,
                 '1790012345001', 'private_company', $name, 0.01, true),
                ('EC-RUC-1760001550001', 'GAD X', 'MANABI', '63', 12.0, 1.0, 0.4,
                 $person, 'natural_person', null, 0.02, true),
                ('EC-RUC-1760001550001', 'GAD X', 'MANABI', '88', 20.0, 0.2, 0.2,
                 $person, 'natural_person', null, 0.9, false)
            ) as t(buyer_id, buyer_name, buyer_region, cpc_division, cell_awards, top_share,
                   typical_top_share, supplier_key, supplier_type, supplier_name, q_value,
                   flagged)
            """,
            {"name": lp01_name, "person": PERSON_KEY},
        )
        con.execute("""
            create table silver.processes as select
                '2025-01' as source_month, 'open' as procurement_method, true as has_award,
                'MANABI' as buyer_region
        """)


def test_exports_every_public_dataset(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)

    report = export_public(db, tmp_path / "public")

    assert set(report.rows) == set(PUBLIC_QUERIES)
    assert {p.stem for p in (tmp_path / "public").glob("*.parquet")} == set(PUBLIC_QUERIES)


def test_only_allowlisted_columns_are_published(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    columns = [
        row[0]
        for row in duckdb.execute(
            "describe select * from read_parquet(?)",
            [str(tmp_path / "public" / "review_priority.parquet")],
        ).fetchall()
    ]
    assert "column_added_later" not in columns


def test_persons_appear_only_as_short_label(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    labels = duckdb.execute(
        "select supplier_label from read_parquet(?) order by 1",
        [str(tmp_path / "public" / "lp01_flags.parquet")],
    ).fetchall()
    assert labels == [("Persona #46249a",), ("RAGA S.A.S.",)]


def test_refuses_to_publish_a_person_ruc(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    # A natural person's RUC (third digit 0-5) leaking through a company name field.
    make_gold(db, lp01_name="JUAN PEREZ 1712345678001")

    with pytest.raises(PublicDataError, match="lp01_flags.supplier_label"):
        export_public(db, tmp_path / "public")

    assert not (tmp_path / "public").exists()
