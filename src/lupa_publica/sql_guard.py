"""First lock on AI-written SQL: only one read-only SELECT over our public tables.

A language model writes the SQL, so we treat it like input from a stranger. This
module parses it (it never runs it) and refuses anything that is not a single SELECT
over the allowlisted tables, or that calls a function able to reach files or settings.
The second lock is the database itself (see ``ask.open_public_data``): even a query that
slipped through here could not read files, attach databases or change settings.
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_ROWS = 200

# Functions that read files, other databases or the environment. The locked database
# already blocks them; refusing them here gives a clear message instead of a crash.
FORBIDDEN_FUNCTIONS = frozenset(
    {
        "read_csv",
        "read_csv_auto",
        "read_parquet",
        "parquet_scan",
        "read_json",
        "read_json_auto",
        "read_json_objects",
        "read_ndjson",
        "read_text",
        "read_blob",
        "sniff_csv",
        "glob",
        "query",
        "query_table",
        "getenv",
        "duckdb_settings",
        "duckdb_secrets",
        "duckdb_extensions",
        "duckdb_databases",
    }
)


class UnsafeQueryError(ValueError):
    """The SQL is not a single read-only query over the public tables."""


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return node.sql_name().lower()


def check_sql(sql: str, allowed_tables: Iterable[str], max_rows: int = MAX_ROWS) -> str:
    """Return a safe version of ``sql`` (with a row limit) or raise UnsafeQueryError."""
    allowed = {name.lower() for name in allowed_tables}
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except ParseError as exc:
        raise UnsafeQueryError(f"not valid SQL: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeQueryError("expected exactly one SQL statement")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeQueryError("only SELECT queries are allowed")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise UnsafeQueryError(f"table functions are not allowed: {table.sql()}")
        if table.args.get("db") or table.args.get("catalog"):
            raise UnsafeQueryError(f"schema-qualified tables are not allowed: {table.sql()}")
        name = table.name.lower()
        if name not in allowed and name not in cte_names:
            raise UnsafeQueryError(f"unknown table: {table.name}")

    for func in tree.find_all(exp.Func):
        name = _function_name(func)
        if name in FORBIDDEN_FUNCTIONS:
            raise UnsafeQueryError(f"function not allowed: {name}")

    limit = tree.args.get("limit")
    current = limit.expression if isinstance(limit, exp.Limit) else None
    keep = isinstance(current, exp.Literal) and current.is_int and int(current.name) <= max_rows
    if not keep:
        tree = tree.limit(max_rows)
    return tree.sql(dialect="duckdb")
