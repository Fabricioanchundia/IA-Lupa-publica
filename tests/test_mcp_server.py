import asyncio
from pathlib import Path
from typing import Any

import duckdb
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from test_export import make_gold

from lupa_publica.ask import open_public_data
from lupa_publica.export import export_public
from lupa_publica.mcp_server import build_server


@pytest.fixture
def server(tmp_path: Path) -> MCPServer:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")
    return build_server(open_public_data(tmp_path / "public"))


def call(server: MCPServer, tool: str, **arguments: Any) -> str:
    result = asyncio.run(server.call_tool(tool, arguments))
    return "\n".join(str(getattr(c, "text", "")) for c in getattr(result, "content", []))


def test_every_tool_is_read_only(server: MCPServer) -> None:
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {
        "describe_data",
        "query_public_data",
        "search_contracts",
        "entity_profile",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)


def test_describe_data_explains_the_tables(server: MCPServer) -> None:
    assert "TABLE processes" in call(server, "describe_data")


def test_query_runs_checked_sql_and_shows_it(server: MCPServer) -> None:
    text = call(server, "query_public_data", sql="select count(*) as n from processes")
    assert "SELECT COUNT(*) AS n FROM processes LIMIT 200" in text
    assert "| 2 |" in text


@pytest.mark.parametrize(
    "sql",
    [
        "drop table processes",
        "select * from read_csv('/etc/passwd')",
        "select * from secrets",
    ],
)
def test_unsafe_sql_is_refused(server: MCPServer, sql: str) -> None:
    with pytest.raises(ToolError, match="Query not run"):
        call(server, "query_public_data", sql=sql)


def test_search_contracts_with_filters(server: MCPServer) -> None:
    assert "Obra vial" in call(server, "search_contracts", text="obra", province="manabi")
    assert "Obra vial" in call(server, "search_contracts", text="obra", year=2025)
    assert call(server, "search_contracts", text="obra", year=2019) == "(no rows)"


def test_search_text_is_a_parameter_not_sql(server: MCPServer) -> None:
    assert call(server, "search_contracts", text="'; drop table processes; --") == "(no rows)"
    assert "| 2 |" in call(server, "query_public_data", sql="select count(*) from processes")


def test_entity_profile_explains_signals_neutrally(server: MCPServer) -> None:
    text = call(server, "entity_profile", name="gad x")
    assert "# GAD X (MANABI)" in text
    assert "Una sola oferta (señal alta)" in text
    assert "not evidence of wrongdoing" in text
    assert "Persona #46249a" in text
    assert call(server, "entity_profile", name="no existe") == "No entity matches 'no existe'."


def test_entity_profile_lists_candidates_instead_of_guessing(tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    with duckdb.connect(str(db)) as con:
        con.execute(
            "insert into silver.processes select * replace ('ocds-9' as ocid, "
            "'EC-RUC-1760009990001' as buyer_id, 'GAD Y' as buyer_name) "
            "from silver.processes limit 1"
        )
    export_public(db, tmp_path / "public")
    server = build_server(open_public_data(tmp_path / "public"))

    text = call(server, "entity_profile", name="gad")
    assert "2 entities match 'gad'" in text
    assert "EC-RUC-1760009990001" in text

    profile = call(server, "entity_profile", name="EC-RUC-1760009990001")
    assert profile.startswith("# GAD Y")
