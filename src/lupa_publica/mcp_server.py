"""MCP server: AI assistants can query Lupa Pública's public data (Phase 8).

MCP (Model Context Protocol) is a standard "plug" between AI assistants (Claude Desktop,
code editors, agents) and tools. With this server an assistant can look up contracts,
read an entity's profile or run its own SQL, and answer with real numbers.

The same rules as `lupa ask` apply (ADR-0006, ADR-0007): only the public datasets are
loaded, the database is locked, and every SQL goes through ``sql_guard``. All tools are
read-only. It runs on your computer over stdio: nothing is exposed to the internet.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from lupa_publica.ask import PUBLIC_TABLES, open_public_data, run_query, show
from lupa_publica.semantic import describe_schema
from lupa_publica.sql_guard import UnsafeQueryError, check_sql

INSTRUCTIONS = """\
Public procurement data of Ecuador (SERCOP open data, OCDS), as published by Lupa Pública.
Start with describe_data to learn the tables. Answer in the user's language and always
say which numbers come from which query. Signals (single bid, short period, supplier
concentration, review priority) are reasons to look closer, NEVER evidence of wrongdoing:
use neutral words. Suppliers shown as 'Persona #xxxxxx' are anonymous natural persons:
never try to identify them.
"""

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
MAX_ROWS_SHOWN = 50

LEVEL_WORDS = {"high": "alta", "medium": "media"}


def markdown_table(columns: Sequence[str], rows: Sequence[tuple[object, ...]]) -> str:
    """A small Markdown table (the format assistants read best)."""
    if not rows:
        return "(no rows)"
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows[:MAX_ROWS_SHOWN]:
        lines.append("| " + " | ".join(show(v).replace("|", "/") for v in row) + " |")
    if len(rows) > MAX_ROWS_SHOWN:
        lines.append(f"... {len(rows) - MAX_ROWS_SHOWN} more rows")
    return "\n".join(lines)


def build_server(con: duckdb.DuckDBPyConnection) -> MCPServer:
    """An MCP server whose tools read ``con`` (a locked database with the public data)."""
    server = MCPServer(name="lupa-publica", instructions=INSTRUCTIONS)
    lock = threading.Lock()  # one DuckDB connection, one query at a time

    def select(
        sql: str, params: Sequence[object] = ()
    ) -> tuple[list[str], list[tuple[object, ...]]]:
        with lock:
            cursor = con.execute(sql, list(params))
            return [d[0] for d in cursor.description or []], cursor.fetchall()

    @server.tool(annotations=READ_ONLY)
    def describe_data() -> str:
        """Tables, columns and real example values of the public data. Call this first."""
        with lock:
            return describe_schema(con)

    @server.tool(annotations=READ_ONLY)
    def query_public_data(sql: str) -> str:
        """Run ONE read-only DuckDB SELECT over the public tables (max 200 rows).

        Writes, file access, other schemas and table functions are refused.
        """
        try:
            safe_sql = check_sql(sql, PUBLIC_TABLES)
            with lock:
                columns, rows = run_query(con, safe_sql)
        except (UnsafeQueryError, duckdb.Error, TimeoutError) as exc:
            raise ToolError(f"Query not run: {exc}") from exc
        return f"SQL used:\n{safe_sql}\n\n{len(rows)} rows\n{markdown_table(columns, rows)}"

    @server.tool(annotations=READ_ONLY)
    def search_contracts(
        text: str = "", province: str = "", year: int | None = None, limit: int = 20
    ) -> str:
        """Find procurement processes by words in the title, entity or supplier.

        province: Ecuadorian province in capitals without accents, e.g. MANABI.
        """
        # Fixed SQL: empty filters switch themselves off, every value is a parameter.
        pattern = f"%{text}%"
        columns, rows = select(
            "SELECT p.month AS mes, b.buyer_name AS entidad, b.buyer_region AS provincia, "
            "p.title AS titulo, p.procedure AS procedimiento, p.amount AS monto, "
            "p.supplier_label AS proveedor, p.single_bid AS una_sola_oferta, p.ocid "
            "FROM processes AS p LEFT JOIN buyers AS b ON p.buyer_id = b.buyer_id "
            "WHERE (p.title ILIKE ? OR b.buyer_name ILIKE ? OR p.supplier_label ILIKE ?) "
            "AND (? = '' OR b.buyer_region = ?) "
            "AND (? = '' OR p.month LIKE ?) "
            "ORDER BY p.amount DESC NULLS LAST LIMIT ?",
            [
                pattern,
                pattern,
                pattern,
                province.upper(),
                province.upper(),
                str(year or ""),
                f"{year}-%",
                max(1, min(limit, MAX_ROWS_SHOWN)),
            ],
        )
        return markdown_table(columns, rows)

    @server.tool(annotations=READ_ONLY)
    def entity_profile(name: str) -> str:
        """Profile of one public entity: totals and risk signals explained in plain Spanish.

        name: the entity's buyer_id, or (part of) its name, e.g. 'HOSPITAL VICENTE CORRAL'.
        If several entities match, returns the candidates instead: call again with the
        buyer_id of the right one.
        """
        _, matches = select(
            "SELECT b.buyer_id, b.buyer_name, b.buyer_region, count(p.ocid) AS processes "
            "FROM buyers AS b LEFT JOIN processes AS p ON p.buyer_id = b.buyer_id "
            "WHERE b.buyer_id = ? OR b.buyer_name ILIKE ? "
            "GROUP BY b.buyer_id, b.buyer_name, b.buyer_region "
            "ORDER BY (b.buyer_id = ?) DESC, processes DESC LIMIT 15",
            [name, f"%{name}%", name],
        )
        if not matches:
            return f"No entity matches '{name}'."
        exact = [m for m in matches if name == m[0] or name.upper() == str(m[1]).upper()]
        if len(matches) > 1 and not exact:
            # Never guess: 'MANTA' matches the municipality, a hospital, the fire department...
            return (
                f"{len(matches)} entities match '{name}'. Call entity_profile again with the "
                "buyer_id of the one you mean:\n"
                + markdown_table(["buyer_id", "entidad", "provincia", "procesos"], matches)
            )
        buyer_id, buyer_name, region, _ = (exact or matches)[0]
        lines = [f"# {buyer_name} ({region or 'sin provincia'})", f"buyer_id: {buyer_id}"]
        _, totals = select(
            "SELECT count(*), sum(amount), min(month), max(month) FROM processes "
            "WHERE buyer_id = ?",
            [buyer_id],
        )
        count, amount, first, last = totals[0]
        lines.append(f"Processes: {count} ({first} to {last}), total US$ {show(amount)}")
        columns, priority = select("SELECT * FROM review_priority WHERE buyer_id = ?", [buyer_id])
        if priority:
            row = dict(zip(columns, priority[0], strict=True))
            lines.append(f"Review priority: {row['review_priority']} ({row['signals']} signals)")
            lines.extend(signal_sentences(row))
        else:
            lines.append("Review priority: insufficient_data (too few processes to compare)")
        columns, top = select(
            "SELECT month AS mes, title AS titulo, amount AS monto, supplier_label AS proveedor "
            "FROM processes WHERE buyer_id = ? ORDER BY amount DESC NULLS LAST LIMIT 5",
            [buyer_id],
        )
        lines += ["", "Largest processes:", markdown_table(columns, top)]
        lines.append("\nSignals are reasons to look closer, not evidence of wrongdoing.")
        return "\n".join(lines)

    return server


def signal_sentences(row: dict[str, object]) -> list[str]:
    """One plain sentence per clear signal (same wording idea as the website)."""
    out: list[str] = []
    if row.get("r018_level") in LEVEL_WORDS:
        out.append(
            f"- Una sola oferta (señal {LEVEL_WORDS[str(row['r018_level'])]}): "
            f"{show(row['r018_flagged'])} de {show(row['r018_evaluated'])} procesos "
            f"competitivos, {show(row['r018_ratio'])} veces lo esperado."
        )
    if row.get("r003_level") in LEVEL_WORDS:
        out.append(
            f"- Plazo corto (señal {LEVEL_WORDS[str(row['r003_level'])]}): "
            f"{show(row['r003_flagged'])} de {show(row['r003_evaluated'])} procesos, "
            f"{show(row['r003_ratio'])} veces lo esperado."
        )
    if row.get("lp01_level") == "signal":
        out.append(f"- Proveedor concentrado en {show(row['lp01_flagged_cells'])} categoría(s).")
    return out


def serve(data_dir: Path) -> None:
    """Run the server over stdio (what Claude Desktop and MCP Inspector use)."""
    build_server(open_public_data(data_dir)).run()
