import json
from pathlib import Path

import duckdb
import pytest
from test_ask import FakeModel
from test_export import make_gold

from lupa_publica.ask import open_public_data
from lupa_publica.ask_gallery import build_gallery, read_questions, write_gallery
from lupa_publica.export import PublicDataError, export_public


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")
    return open_public_data(tmp_path / "public")


def test_reads_questions_skipping_comments(tmp_path: Path) -> None:
    path = tmp_path / "q.txt"
    path.write_text("# comment\n\n¿Uno?\n  ¿Dos?  \n", encoding="utf-8")
    assert read_questions(path) == ["¿Uno?", "¿Dos?"]


def test_gallery_keeps_answers_and_refusals_but_not_failures(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    model = FakeModel(
        "select count(*) as procesos from processes",
        "Hay 2 procesos.",
        "NO_SQL: no publicamos cédulas.",
        "select * from secrets",
        "select * from secrets",
    )
    seen: list[int] = []

    gallery, report = build_gallery(
        ["¿Cuántos procesos?", "¿Cédula?", "¿Secretos?"],
        model,
        con,
        "fake-model",
        progress=lambda n, total, q: seen.append(n),
    )
    write_gallery(gallery, tmp_path / "out" / "gallery.json")

    saved = json.loads((tmp_path / "out" / "gallery.json").read_text(encoding="utf-8"))
    assert [e["question"] for e in saved["examples"]] == ["¿Cuántos procesos?", "¿Cédula?"]
    assert saved["examples"][0]["rows"] == [[2]]
    assert saved["examples"][1]["refusal"] == "no publicamos cédulas."
    assert saved["model"] == "fake-model"
    assert (report.answered, report.refused, len(report.failed)) == (1, 1, 1)
    assert seen == [1, 2, 3]


def test_refuses_to_write_personal_identifiers(tmp_path: Path) -> None:
    gallery = {"examples": [{"explanation": "El proveedor 1712345678001 ganó."}]}
    with pytest.raises(PublicDataError):
        write_gallery(gallery, tmp_path / "gallery.json")
    assert not (tmp_path / "gallery.json").exists()
