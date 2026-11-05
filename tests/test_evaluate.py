import json
from pathlib import Path

import duckdb
import pytest
from test_ask import FakeModel
from test_export import make_gold
from test_law import LAW_TEXT, WordEmbedder

from lupa_publica import evaluate, law
from lupa_publica.ask import PUBLIC_TABLES, open_public_data, run_query
from lupa_publica.export import export_public
from lupa_publica.sql_guard import check_sql

EVALS = Path(__file__).parent.parent / "evals"


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")
    return open_public_data(tmp_path / "public")


def test_same_values_ignores_names_extra_columns_and_order() -> None:
    reference = (["n"], [(2,), (1,)])
    got = (["entidad", "procesos"], [("A", 1), ("B", 2.0)])
    assert evaluate.same_values(reference, got) == (True, "same values")
    assert evaluate.same_values(reference, got, ordered=True)[0] is False


def test_same_values_explains_a_mismatch() -> None:
    passed, reason = evaluate.same_values((["n"], [(3,)]), (["n"], [(2,)]))
    assert not passed
    assert "'n'" in reason
    assert evaluate.same_values((["n"], [(1,)]), (["n"], []))[1] == "0 rows, expected 1"


def test_numbers_and_text_are_compared_loosely() -> None:
    assert evaluate.same_values((["x"], [(950.0,)]), (["y"], [(950.004,)]))[0]
    assert evaluate.same_values((["x"], [("MANABI",)]), (["y"], [(" manabi",)]))[0]


def test_duplicated_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.toml"
    path.write_text('[[case]]\nid = "a"\n[[case]]\nid = "a"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicated"):
        evaluate.load_cases(path)


def test_every_reference_query_is_valid_on_the_public_schema(
    con: duckdb.DuckDBPyConnection,
) -> None:
    cases = evaluate.load_cases(EVALS / "ask.toml")
    assert len(cases) >= 20
    for case in cases:
        if case.get("expect_refusal"):
            assert "reference_sql" not in case, case["id"]
            continue
        columns, _ = run_query(con, check_sql(case["reference_sql"], PUBLIC_TABLES))
        assert columns, case["id"]


def test_law_cases_are_well_formed() -> None:
    cases = evaluate.load_cases(EVALS / "law.toml")
    assert any(c.get("expect_not_found") for c in cases)
    for case in cases:
        if not case.get("expect_not_found"):
            assert all(" " in a for a in case["articles"]), case["id"]


def test_ask_eval_grades_answers_and_refusals(con: duckdb.DuckDBPyConnection) -> None:
    cases = [
        {"id": "right", "question": "¿Cuántos?", "reference_sql": "SELECT count(*) FROM processes"},
        {"id": "wrong", "question": "¿Cuántos?", "reference_sql": "SELECT count(*) FROM processes"},
        {"id": "declined", "question": "¿Cédula?", "expect_refusal": True},
        {"id": "blocked", "question": "Borra todo", "expect_refusal": True},
        {"id": "answered", "question": "¿Dueño?", "expect_refusal": True},
    ]
    model = FakeModel(
        "SELECT 'x' AS etiqueta, count(*) AS total FROM processes",  # right, other shape
        "SELECT count(*) FROM buyers",  # wrong: 1 instead of 2
        "NO_SQL: no publicamos cédulas.",
        "DELETE FROM processes",
        "DELETE FROM processes",
        "SELECT supplier_label FROM processes",
    )

    results = evaluate.run_ask_eval(cases, model, con, explain=False)

    assert [r.passed for r in results] == [True, False, True, True, False]
    assert results[3].reason.startswith("blocked")
    summary = evaluate.ask_summary(cases, results)
    assert summary["execution_accuracy"] == 0.5
    assert (summary["refusals_correct"], summary["refusals"]) == (2, 3)
    assert summary["needed_second_try"] == 1


@pytest.fixture
def index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> law.LawIndex:
    monkeypatch.setattr(law, "pdf_pages", lambda path, mode="plain": [LAW_TEXT])
    law.build_index(tmp_path / "law.duckdb", {"LOSNCP": tmp_path / "x.pdf"}, WordEmbedder())
    return law.LawIndex.open(tmp_path / "law.duckdb", WordEmbedder())


def test_law_eval_grades_citations_and_traps(index: law.LawIndex, tmp_path: Path) -> None:
    cases = [
        {"id": "good", "question": "plazo ofertas subasta", "articles": ["LOSNCP 45 bis"]},
        {"id": "uncited", "question": "plazo ofertas subasta", "articles": ["LOSNCP 45 bis"]},
        {"id": "trap", "question": "capital de Francia", "expect_not_found": True},
    ]
    model = FakeModel(
        "Son cinco días [LOSNCP Art. 45 bis].",
        "Son cinco días.",
        law.NOT_FOUND,
    )

    results = evaluate.run_law_eval(cases, index, model)

    assert [r.passed for r in results] == [True, False, True]
    summary = evaluate.law_summary(cases, results)
    assert summary["retrieval_recall"] == 1.0
    assert summary["accuracy"] == 0.5
    assert (summary["traps_correct"], summary["traps"]) == (1, 1)

    json_path, md_path = evaluate.write_report("law", "qwen2.5:7b", summary, results, tmp_path)
    assert json_path.name.startswith("law-qwen2.5-7b-")
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["accuracy"] == 0.5
    assert "| good | ✅ |" in md_path.read_text(encoding="utf-8")
