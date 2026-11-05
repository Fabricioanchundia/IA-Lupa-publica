import pytest

from lupa_publica.sql_guard import MAX_ROWS, UnsafeQueryError, check_sql

TABLES = ["processes", "buyers"]


@pytest.mark.parametrize(
    "sql",
    [
        "select count(*) from processes",
        "select b.buyer_name, sum(p.amount) from processes p join buyers b "
        "on p.buyer_id = b.buyer_id group by 1 order by 2 desc",
        "with big as (select * from processes where amount > 1000) select count(*) from big",
        "select ocid from processes union all select buyer_id from buyers",
    ],
)
def test_accepts_read_only_queries(sql: str) -> None:
    assert check_sql(sql, TABLES).endswith(f"LIMIT {MAX_ROWS}")


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("drop table processes", "only SELECT"),
        ("delete from processes", "only SELECT"),
        ("insert into processes select * from processes", "only SELECT"),
        ("attach 'other.duckdb'", "only SELECT"),
        ("copy processes to 'leak.csv'", "only SELECT"),
        ("pragma database_list", "only SELECT"),
        ("select 1; drop table processes", "exactly one"),
        ("select * from read_csv('/etc/passwd')", "table functions"),
        ("select * from '/etc/passwd'", "unknown table"),
        ("select read_text('/etc/passwd')", "function not allowed"),
        ("select getenv('HOME')", "function not allowed"),
        ("select * from main.processes", "schema-qualified"),
        ("select * from gold.buyer_review_priority", "schema-qualified"),
        ("select * from stg_award_suppliers", "unknown table"),
        ("this is not sql at all", "not valid SQL|only SELECT"),
    ],
)
def test_refuses_anything_else(sql: str, reason: str) -> None:
    with pytest.raises(UnsafeQueryError, match=reason):
        check_sql(sql, TABLES)


def test_keeps_a_small_limit_and_caps_a_big_one() -> None:
    assert check_sql("select * from processes limit 5", TABLES).endswith("LIMIT 5")
    assert check_sql("select * from processes limit 99999", TABLES).endswith(f"LIMIT {MAX_ROWS}")
