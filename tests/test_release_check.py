import re
from pathlib import Path

import duckdb
import pytest

from lupa_publica.cli import build_parser, main
from lupa_publica.export import PUBLIC_QUERIES
from lupa_publica.release_check import check_release, count_rows, to_markdown

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def write_export(folder: Path, rows: int, *, sizes: dict[str, int] | None = None) -> Path:
    """Fake public datasets: every file has ``rows`` rows unless ``sizes`` says otherwise."""
    folder.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as con:
        for name in PUBLIC_QUERIES:
            n = (sizes or {}).get(name, rows)
            target = folder / f"{name}.csv.gz"
            con.execute(
                f"copy (select i as id, 'texto, con coma' as t from range({n}) r(i)) "  # noqa: S608
                f"to '{target}' (format csv, header, compression gzip)"
            )
    return folder


def test_counts_rows_without_the_header(tmp_path: Path) -> None:
    folder = write_export(tmp_path / "new", 5)
    assert count_rows(folder / "processes.csv.gz") == 5


def test_first_release_only_needs_every_dataset(tmp_path: Path) -> None:
    check = check_release(write_export(tmp_path / "new", 3), tmp_path / "no-previous")

    assert check.ok
    assert not check.compared
    assert "No hay una publicación anterior" in to_markdown(check)


def test_a_normal_month_can_be_published(tmp_path: Path) -> None:
    previous = write_export(tmp_path / "old", 100)
    current = write_export(tmp_path / "new", 100, sizes={"processes": 95})

    check = check_release(current, previous)

    assert check.ok
    assert "| processes | 100 | 95 | -5.0% |" in to_markdown(check)


def test_a_big_fall_stops_the_release(tmp_path: Path) -> None:
    previous = write_export(tmp_path / "old", 100)
    current = write_export(tmp_path / "new", 100, sizes={"processes": 40})

    check = check_release(current, previous)

    assert not check.ok
    assert "processes fell from 100 to 40" in check.problems[0]
    assert "❌ No se publica" in to_markdown(check)


def test_missing_or_empty_datasets_stop_the_release(tmp_path: Path) -> None:
    current = write_export(tmp_path / "new", 10, sizes={"buyers": 0})
    (current / "review_priority.csv.gz").unlink()

    problems = check_release(current).problems

    assert "buyers is empty" in problems
    assert "review_priority.csv.gz is missing" in problems


def test_cli_exit_code_and_summary_file(tmp_path: Path) -> None:
    previous = write_export(tmp_path / "old", 100)
    current = write_export(tmp_path / "new", 100, sizes={"processes": 10})
    summary = tmp_path / "summary.md"
    args = ["check-release", "--data", str(current), "--previous", str(previous)]

    assert main([*args, "--summary", str(summary)]) == 1
    assert "processes fell" in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_workflows_only_use_real_commands(workflow: Path) -> None:
    # The refresh runs once a month: a typo there would only show up a month later.
    commands = build_parser()._subparsers._group_actions[0].choices  # type: ignore[union-attr]
    used = re.findall(r"uv run lupa ([a-z-]+)", workflow.read_text(encoding="utf-8"))
    assert all(command in commands for command in used), used
