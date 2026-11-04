from pathlib import Path

import duckdb
import pytest

from lupa_publica.export import PUBLIC_QUERIES, PublicDataError, export_public
from lupa_publica.privacy import MissingKeyError

PERSON_KEY = "46249a" + "b" * 58  # a full 64-character pseudonym


def make_gold(db_path: Path, *, lp01_name: str = "RAGA S.A.S.", title: str = "Obra vial") -> None:
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
        con.execute(
            """
            create table silver.processes as select * from (values
                ('ocds-1', '2025-01', 'EC-RUC-1760001550001', 'GAD X', 'MANABI', 'open',
                 'Licitación', $title, 1000.0, 1, true),
                ('ocds-2', '2025-02', 'EC-RUC-1760001550001', 'GAD X', 'MANABI', 'direct',
                 'Catálogo electrónico', 'Compra de papel', null, null, true)
            ) t(ocid, source_month, buyer_id, buyer_name, buyer_region, procurement_method,
                procurement_method_details, tender_title, tender_amount, number_of_tenderers,
                has_award)
            """,
            {"title": title},
        )
        con.execute("""
            create table silver.stg_awards as select * from (values
                ('ocds-1', 'a1', 900.0), ('ocds-2', 'a1', 50.0)
            ) t(ocid, award_id, award_amount)
        """)
        con.execute(
            """
            create table silver.stg_award_suppliers as select * from (values
                ('ocds-1', 'a1', $person, 'natural_person', null),
                ('ocds-2', 'a1', '1790012345001', 'private_company', 'PAPELERA S.A.')
            ) t(ocid, award_id, supplier_key, supplier_type, supplier_name)
            """,
            {"person": PERSON_KEY},
        )
        con.execute("""
            create table silver.int_process_main_cpc as
            select 'ocds-1' as ocid, '54' as main_cpc_division
        """)
        con.execute("""
            create table gold.indicator_r018_single_bid as select 'ocds-1' as ocid, true as flagged
        """)
        con.execute("""
            create table gold.indicator_r003_short_period as
            select 'ocds-1' as ocid, false as flagged
        """)


def test_exports_every_public_dataset(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)

    report = export_public(db, tmp_path / "public")

    assert set(report.rows) == set(PUBLIC_QUERIES)
    assert {p.name for p in (tmp_path / "public").glob("*.csv.gz")} == {
        f"{name}.csv.gz" for name in PUBLIC_QUERIES
    }


def test_only_allowlisted_columns_are_published(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    columns = [
        row[0]
        for row in duckdb.execute(
            "describe select * from read_csv(?)",
            [str(tmp_path / "public" / "review_priority.csv.gz")],
        ).fetchall()
    ]
    assert "column_added_later" not in columns


def test_persons_appear_only_as_short_label(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    labels = duckdb.execute(
        "select supplier_label from read_csv(?) order by 1",
        [str(tmp_path / "public" / "lp01_flags.csv.gz")],
    ).fetchall()
    assert labels == [("Persona #46249a",), ("RAGA S.A.S.",)]


def test_refuses_to_publish_a_person_ruc(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    # A natural person's RUC (third digit 0-5) leaking through a company name field.
    make_gold(db, lp01_name="JUAN PEREZ 1712345678001")

    with pytest.raises(PublicDataError, match="lp01_flags.supplier_label"):
        export_public(db, tmp_path / "public")

    assert not (tmp_path / "public").exists()


def read_public(path: Path) -> list[tuple[object, ...]]:
    return duckdb.execute("select * from read_csv(?) order by 1", [str(path)]).fetchall()


def test_processes_are_public_with_signals_and_labels(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    rows = duckdb.execute(
        "select ocid, amount, single_bid, supplier_label from read_csv(?) order by ocid",
        [str(tmp_path / "public" / "processes.csv.gz")],
    ).fetchall()
    assert rows == [
        ("ocds-1", 900.0, True, "Persona #46249a"),
        ("ocds-2", 50.0, False, "PAPELERA S.A."),
    ]


def test_hides_identity_numbers_in_titles(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db, title="Pago a 1712345678 y 0912345678001; empresa 1790012345001")
    export_public(db, tmp_path / "public")

    (title,) = duckdb.execute(
        "select title from read_csv(?) where ocid = 'ocds-1'",
        [str(tmp_path / "public" / "processes.csv.gz")],
    ).fetchone() or ("",)
    assert title == (
        "Pago a [identificación oculta] y [identificación oculta]; empresa 1790012345001"
    )


TEST_KEY = "ab" * 32


def make_person_buyer(db: Path) -> None:
    """A notary office registered with the notary's own RUC (third digit 0-5)."""
    with duckdb.connect(str(db)) as con:
        for table in [
            "silver.processes",
            "gold.buyer_review_priority",
            "gold.buyer_r018_summary",
            "gold.buyer_r003_summary",
            "gold.indicator_lp01_supplier_concentration",
        ]:
            con.execute(f"update {table} set buyer_id = 'EC-RUC-1712345678001-77'")  # noqa: S608


def test_a_person_buyer_without_the_key_gives_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LUPA_PSEUDONYM_KEY", raising=False)
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    make_person_buyer(db)

    with pytest.raises(MissingKeyError, match="source .env"):
        export_public(db, tmp_path / "public")
    assert not (tmp_path / "public").exists()


def test_buyers_registered_with_a_person_number_get_an_opaque_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUPA_PSEUDONYM_KEY", TEST_KEY)
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    make_person_buyer(db)

    export_public(db, tmp_path / "public")

    ids = {
        row[0]
        for name in ["processes", "buyers", "review_priority", "lp01_flags"]
        for row in duckdb.execute(
            "select distinct buyer_id from read_csv(?)",
            [str(tmp_path / "public" / f"{name}.csv.gz")],
        ).fetchall()
    }
    assert len(ids) == 1  # the same opaque id everywhere, so the pages still link
    (only,) = ids
    assert only.startswith("entidad-")
    assert "1712345678" not in only


def test_public_entity_ids_are_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUPA_PSEUDONYM_KEY", raising=False)  # not needed for entities
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")

    rows = duckdb.execute(
        "select distinct buyer_id from read_csv(?)",
        [str(tmp_path / "public" / "buyers.csv.gz")],
    ).fetchall()
    assert rows == [("EC-RUC-1760001550001",)]
