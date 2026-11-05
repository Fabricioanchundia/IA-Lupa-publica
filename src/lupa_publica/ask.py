"""Ask questions in Spanish about the public data (Phase 7: Text-to-SQL).

How an answer is made:
1. The model gets the question plus a description of the PUBLIC tables (never the data).
2. It writes one SQL query.
3. Lock 1 (sql_guard): only a single SELECT over the public tables is accepted.
4. Lock 2 (the database): it holds only the public datasets and cannot read files,
   attach databases or change its own settings, and every query has a time limit.
5. If the query is refused or fails, the model sees the error and gets one more try.
6. The model explains the result in simple Spanish, using only the numbers it got.

The numbers always come from the data, never from the model's memory, and the SQL is
shown with every answer so anyone can check it.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from lupa_publica.llm import LanguageModel, Message
from lupa_publica.semantic import TABLES, describe_schema
from lupa_publica.sql_guard import UnsafeQueryError, check_sql

PUBLIC_TABLES = tuple(TABLES)
# Codes and ids stay text, so '01' never turns into the number 1 (same as the website).
TEXT_COLUMNS: dict[str, tuple[str, ...]] = {
    "processes": ("ocid", "month", "buyer_id", "cpc_division"),
    "buyers": ("buyer_id",),
    "cpc_divisions": ("cpc_division",),
    "review_priority": ("buyer_id",),
    "r018_buyers": ("buyer_id",),
    "r003_buyers": ("buyer_id",),
    "lp01_flags": ("buyer_id", "cpc_division"),
    "monthly_coverage": ("source_month",),
}
QUERY_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 2
ROWS_FOR_EXPLANATION = 20
NO_SQL = "NO_SQL:"

SQL_RULES = """\
You translate questions about public procurement in Ecuador into ONE DuckDB SQL query.
Rules:
- Use only the tables and columns described below. Write a single SELECT (CTEs allowed).
- Match names and free text with ILIKE and wildcards, e.g. buyer_name ILIKE '%MANTA%'.
- Provinces are stored in CAPITALS without accents, e.g. 'MANABI', 'LOS RIOS'.
- Years: month LIKE '2025-%'. Amounts are US dollars.
- Give readable column aliases in Spanish (e.g. AS monto_total).
- Signals (single_bid, short_period, review_priority...) are risk signals, not proof of
  wrongdoing.
- Never try to identify people behind 'Persona #...' labels. Counting or adding them up
  (how many, how much) is fine: only identifying one person must be declined.
- If the data cannot answer the question, reply exactly: NO_SQL: <short reason in Spanish>
Reply with the SQL only, inside a ```sql code block.
"""

EXAMPLES: tuple[tuple[str, str], ...] = (
    (
        "¿Cuántos procesos publicaron las entidades de Manabí en 2025?",
        "SELECT count(*) AS procesos\nFROM processes AS p\n"
        "JOIN buyers AS b ON p.buyer_id = b.buyer_id\n"
        "WHERE b.buyer_region = 'MANABI' AND p.month LIKE '2025-%'",
    ),
    (
        "¿Qué entidades hay que revisar primero?",
        "SELECT buyer_name AS entidad, buyer_region AS provincia, signals AS senales\n"
        "FROM review_priority\nWHERE review_priority = 'review_first'\n"
        "ORDER BY signals DESC, buyer_name",
    ),
    (
        "¿Cuáles son los 5 proveedores con más monto en obras de construcción?",
        "SELECT p.supplier_label AS proveedor, sum(p.amount) AS monto_total\n"
        "FROM processes AS p\nJOIN cpc_divisions AS c ON p.cpc_division = c.cpc_division\n"
        "WHERE c.name ILIKE '%construcción%'\nGROUP BY 1\nORDER BY monto_total DESC\nLIMIT 5",
    ),
    (
        "¿Cuál es el número de cédula del proveedor Persona #46249a?",
        "NO_SQL: Lupa Pública no publica datos que identifiquen a personas naturales.",
    ),
)

EXPLAIN_RULES = """\
You explain the result of a database query to people who are not engineers, in simple
Spanish, in 2 to 4 sentences.
- Use ONLY numbers that appear in the result; never add or estimate others.
- Do not count rows yourself: when you say how many there are, use the row count given.
- Copy names exactly as written (you may change CAPITALS to normal case); do not
  translate or expand abbreviations.
- Round amounts to whole dollars and write them like 'US$ 1.234.567'. If the result is
  empty, say that no data matched.
- Signals are reasons to look closer, never accusations: use neutral words.
"""


@dataclass
class Answer:
    question: str
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple[object, ...]] = field(default_factory=list)
    explanation: str = ""
    unverified_numbers: list[str] = field(default_factory=list)
    refusal: str | None = None
    error: str | None = None
    attempts: int = 0

    @property
    def ok(self) -> bool:
        return self.sql is not None and self.error is None and self.refusal is None


def open_public_data(data_dir: Path) -> duckdb.DuckDBPyConnection:
    """An in-memory database with the public datasets only, then locked down."""
    con = duckdb.connect(":memory:", config={"memory_limit": "2GB", "threads": "2"})
    for table in PUBLIC_TABLES:
        path = data_dir / f"{table}.csv.gz"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run: uv run lupa export-public")
        types = ", ".join(f"'{column}': 'VARCHAR'" for column in TEXT_COLUMNS.get(table, ()))
        # Table and column names are our own constants; the path is a parameter.
        con.execute(
            f"create table {table} as select * from read_csv(?, header = true, "  # noqa: S608
            f"types = {{{types}}})",
            [str(path)],
        )
    lock(con)
    return con


def lock(con: duckdb.DuckDBPyConnection) -> None:
    """Lock 2: no files, no network, no extensions, and settings frozen."""
    con.execute("set autoinstall_known_extensions = false")
    con.execute("set autoload_known_extensions = false")
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")


def run_query(
    con: duckdb.DuckDBPyConnection, sql: str, timeout: float = QUERY_TIMEOUT_SECONDS
) -> tuple[list[str], list[tuple[object, ...]]]:
    """Run an already checked query, stopping it if it takes too long."""
    timer = threading.Timer(timeout, con.interrupt)
    timer.start()
    try:
        cursor = con.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        return columns, cursor.fetchall()
    except duckdb.InterruptException as exc:
        raise TimeoutError(f"the query took more than {timeout:.0f} seconds") from exc
    finally:
        timer.cancel()


def extract_sql(reply: str) -> str:
    """The SQL inside the model's reply (it may come in a ```sql block or bare)."""
    block = re.search(r"```(?:sql)?\s*(.*?)```", reply, flags=re.DOTALL | re.IGNORECASE)
    return (block.group(1) if block else reply).strip().rstrip(";").strip()


def sql_messages(schema: str, question: str) -> list[Message]:
    messages = [Message("system", f"{SQL_RULES}\n{schema}")]
    for example_question, example_sql in EXAMPLES:
        messages.append(Message("user", example_question))
        reply = example_sql if example_sql.startswith(NO_SQL) else f"```sql\n{example_sql}\n```"
        messages.append(Message("assistant", reply))
    messages.append(Message("user", question))
    return messages


def show(value: object) -> str:
    """A value as text; decimals rounded to 2 (sums of dollars come out as 351703797.68000007)."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:.0f}"
    return str(value)


def as_csv(columns: Sequence[str], rows: Sequence[tuple[object, ...]]) -> str:
    lines = [",".join(columns)]
    lines += [",".join(show(v) for v in row) for row in rows]
    return "\n".join(lines)


def ask(
    question: str,
    model: LanguageModel,
    con: duckdb.DuckDBPyConnection,
    explain: bool = True,
) -> Answer:
    """Answer ``question`` from the public data. Never raises for a bad model reply."""
    answer = Answer(question=question)
    messages = sql_messages(describe_schema(con), question)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        answer.attempts = attempt
        reply = model.complete(messages)
        if reply.strip().startswith(NO_SQL):
            answer.refusal = reply.strip()[len(NO_SQL) :].strip()
            return answer
        try:
            safe_sql = check_sql(extract_sql(reply), PUBLIC_TABLES)
            answer.columns, answer.rows = run_query(con, safe_sql)
        except (UnsafeQueryError, duckdb.Error, TimeoutError) as exc:
            answer.error = str(exc)
            messages += [
                Message("assistant", reply),
                Message("user", f"That query failed: {exc}\nWrite a corrected query."),
            ]
            continue
        answer.sql, answer.error = safe_sql, None
        break
    if answer.ok and explain:
        result = as_csv(answer.columns, answer.rows[:ROWS_FOR_EXPLANATION])
        answer.explanation = model.complete(
            [
                Message("system", EXPLAIN_RULES),
                Message(
                    "user",
                    f"Question: {question}\nSQL: {answer.sql}\n"
                    f"Row count: {len(answer.rows)}\nResult (CSV):\n{result}",
                ),
            ]
        ).strip()
        answer.unverified_numbers = unverified_numbers(
            answer.explanation, answer.rows, extra=f"{question} {answer.sql} {len(answer.rows)}"
        )
    return answer


NUMBER = re.compile(r"\d[\d.,]*\d|\d")
LIST_MARKER = re.compile(r"^\s*\d+[.)]\s", flags=re.MULTILINE)


def parse_number(token: str) -> float | None:
    """'1.234.567,8' (Spanish) or '1,234,567.8' (English) or '45' -> float."""
    dots, commas = token.count("."), token.count(",")
    if dots and commas:
        decimal = "." if token.rfind(".") > token.rfind(",") else ","
    elif dots or commas:
        sep = "." if dots else ","
        groups = token.split(sep)
        thousands = len(groups) > 2 or len(groups[-1]) == 3
        decimal = "" if thousands else sep
    else:
        decimal = ""
    digits = "".join(c if c.isdigit() else ("." if c == decimal else "") for c in token)
    try:
        return float(digits)
    except ValueError:
        return None


def unverified_numbers(text: str, rows: Sequence[tuple[object, ...]], extra: str = "") -> list[str]:
    """Numbers in ``text`` that match no value of the result (nor the question or SQL).

    A cheap safety net for the explanation: the table is always right because it comes
    from the data, but the model writing the sentence can still slip. Percentages of a
    0-1 share and rounded amounts count as matches.
    """
    known: list[float] = []
    for row in rows:
        for value in row:
            if isinstance(value, int | float) and not isinstance(value, bool):
                known += [float(value), float(value) * 100]
            elif isinstance(value, str):
                known += [n for t in NUMBER.findall(value) if (n := parse_number(t)) is not None]
    known += [n for t in NUMBER.findall(extra) if (n := parse_number(t)) is not None]
    problems: list[str] = []
    # "1. Hospital ..." list numbers are not data.
    text = LIST_MARKER.sub("", text)
    for token in NUMBER.findall(text):
        value = parse_number(token)
        if value is None:
            continue
        if not any(abs(value - k) <= max(0.5, 0.005 * abs(k)) for k in known):
            problems.append(token)
    return problems
