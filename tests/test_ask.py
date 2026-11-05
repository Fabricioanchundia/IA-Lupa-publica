from collections.abc import Iterator
from pathlib import Path

import duckdb
import httpx
import pytest
from test_export import make_gold

from lupa_publica import cli
from lupa_publica.ask import (
    EXAMPLES,
    NO_SQL,
    PUBLIC_TABLES,
    ask,
    open_public_data,
    parse_number,
    run_query,
    unverified_numbers,
)
from lupa_publica.export import export_public
from lupa_publica.llm import LLMError, Message, OllamaModel
from lupa_publica.semantic import describe_schema, undocumented_columns
from lupa_publica.sql_guard import check_sql


class FakeModel:
    """Answers with prepared replies, in order, and remembers what it was asked."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> str:
        self.calls.append(list(messages))
        return self.replies.pop(0)


@pytest.fixture
def public_dir(tmp_path: Path) -> Path:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")
    return tmp_path / "public"


@pytest.fixture
def con(public_dir: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_public_data(public_dir)
    yield connection
    connection.close()


def test_every_public_column_is_explained_to_the_model(con: duckdb.DuckDBPyConnection) -> None:
    assert undocumented_columns(con) == []


def test_schema_includes_real_values(con: duckdb.DuckDBPyConnection) -> None:
    schema = describe_schema(con)
    assert "TABLE processes" in schema
    assert "'MANABI'" in schema


def test_locked_database_cannot_read_files(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(duckdb.Error):
        con.execute("select * from read_csv('/etc/passwd')")
    with pytest.raises(duckdb.Error):
        con.execute("set enable_external_access = true")


def test_slow_queries_are_stopped(con: duckdb.DuckDBPyConnection) -> None:
    with pytest.raises(TimeoutError):
        run_query(con, "select count(*) from range(100000) a, range(100000) b", timeout=0.2)


def test_answers_with_checked_sql_and_explanation(con: duckdb.DuckDBPyConnection) -> None:
    model = FakeModel(
        "```sql\nselect count(*) as procesos from processes;\n```",
        "Hay 2 procesos.",
    )

    answer = ask("¿Cuántos procesos hay?", model, con)

    assert answer.ok
    assert answer.rows == [(2,)]
    assert answer.sql is not None and "LIMIT" in answer.sql
    assert answer.explanation == "Hay 2 procesos."
    # The explanation step only sees the question, the SQL and the result.
    explain_prompt = model.calls[1][-1].content
    assert "procesos" in explain_prompt and "2" in explain_prompt


def test_a_refused_query_gets_one_more_try_with_the_error(
    con: duckdb.DuckDBPyConnection,
) -> None:
    model = FakeModel("drop table processes", "select count(*) as n from buyers", "Hay 1.")

    answer = ask("¿Cuántas entidades hay?", model, con)

    assert answer.ok and answer.attempts == 2
    assert "only SELECT" in model.calls[1][-1].content
    assert con.execute("select count(*) from processes").fetchone() == (2,)


def test_gives_up_after_two_bad_queries(con: duckdb.DuckDBPyConnection) -> None:
    model = FakeModel("select * from secrets", "select * from secrets")

    answer = ask("dame los secretos", model, con)

    assert not answer.ok
    assert answer.attempts == 2
    assert answer.error is not None and "unknown table" in answer.error


def test_the_model_can_decline(con: duckdb.DuckDBPyConnection) -> None:
    model = FakeModel("NO_SQL: no publicamos cédulas.")

    answer = ask("¿Cuál es la cédula de Persona #46249a?", model, con)

    assert answer.refusal == "no publicamos cédulas."
    assert answer.sql is None


def test_ollama_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "SELECT 1"}})

    model = OllamaModel(
        model="test-model",
        base_url="http://ollama.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert model.complete([Message("user", "hola")]) == "SELECT 1"
    assert seen["url"] == "http://ollama.test/api/chat"
    assert '"temperature": 0' in str(seen["body"]) or '"temperature":0' in str(seen["body"])


def test_missing_model_says_how_to_download_it() -> None:
    model = OllamaModel(
        model="qwen2.5-coder:7b",
        base_url="http://ollama.test",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))),
    )
    with pytest.raises(LLMError, match="ollama pull qwen2.5-coder:7b"):
        model.complete([Message("user", "hola")])


def test_cli_ask_prints_sql_and_table(
    public_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeModel("select count(*) as procesos from processes", "Hay 2 procesos.")
    monkeypatch.setattr(cli, "OllamaModel", lambda model=None: fake)

    code = cli.main(["ask", "¿Cuántos procesos hay?", "--public-data", str(public_dir)])

    out = capsys.readouterr().out
    assert code == 0
    assert "SELECT COUNT(*) AS procesos FROM processes LIMIT 200" in out
    assert "Hay 2 procesos." in out


@pytest.mark.parametrize("example", [sql for _, sql in EXAMPLES if not sql.startswith(NO_SQL)])
def test_the_examples_shown_to_the_model_really_work(
    con: duckdb.DuckDBPyConnection, example: str
) -> None:
    columns, _ = run_query(con, check_sql(example, PUBLIC_TABLES))
    assert columns


@pytest.mark.parametrize(
    ("token", "value"),
    [
        ("12", 12.0),
        ("1.234.567", 1234567.0),
        ("1,234,567", 1234567.0),
        ("1.234.567,89", 1234567.89),
        ("12,5", 12.5),
        ("3.5", 3.5),
    ],
)
def test_reads_spanish_and_english_numbers(token: str, value: float) -> None:
    assert parse_number(token) == value


def test_flags_numbers_that_are_not_in_the_result() -> None:
    rows = [("GAD X", 2, 1234567.4, 0.45)]
    text = "GAD X tiene 2 señales, US$ 1.234.567 y 45 % con una oferta; en total 99 casos."
    assert unverified_numbers(text, rows) == ["99"]


def test_explanation_with_an_invented_number_is_marked(con: duckdb.DuckDBPyConnection) -> None:
    model = FakeModel("select count(*) as procesos from processes", "Hay 7 procesos.")

    answer = ask("¿Cuántos procesos hay en 2025?", model, con)

    assert answer.rows == [(2,)]
    assert answer.unverified_numbers == ["7"]
