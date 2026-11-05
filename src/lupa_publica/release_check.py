"""Safety brake before the monthly robot publishes new data (Phase 10, ADR-0010).

The refresh runs on GitHub Actions with nobody watching. SERCOP sometimes answers with
cut or empty files, and a bug could produce an almost empty export. Before a new data
release is published, the new datasets are compared with the ones the website uses now:
if a dataset is missing or empty, or the main table shrank too much, publishing stops and
a person has to look. Old data on the website is better than broken data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from lupa_publica.export import PUBLIC_QUERIES

MAIN_DATASET = "processes"
# Moving the 24-month window drops the oldest month (up to ~8% of the processes) and adds a
# new one, so a normal month changes the total a little. A fall of more than 20% is not normal.
DEFAULT_MIN_RATIO = 0.8


@dataclass(frozen=True)
class DatasetChange:
    name: str
    previous: int | None
    current: int | None

    @property
    def change(self) -> str:
        if self.previous is None or self.current is None:
            return "—"
        if self.previous == 0:
            return "nuevo" if self.current else "0 %"
        return f"{(self.current - self.previous) / self.previous:+.1%}"


@dataclass
class ReleaseCheck:
    changes: list[DatasetChange] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    compared: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems


def count_rows(path: Path) -> int:
    """Rows of a gzipped CSV written by ``export_public`` (header not counted)."""
    with duckdb.connect() as con:
        row = con.execute(
            "select count(*) from read_csv(?, header = true, all_varchar = true)", [str(path)]
        ).fetchone()
    return int(row[0]) if row else 0


def _rows_in(folder: Path | None, name: str) -> int | None:
    if folder is None:
        return None
    path = folder / f"{name}.csv.gz"
    return count_rows(path) if path.exists() else None


def check_release(
    current_dir: Path, previous_dir: Path | None = None, min_ratio: float = DEFAULT_MIN_RATIO
) -> ReleaseCheck:
    """Compare a new export with the previous release (if there is one)."""
    if previous_dir is not None and not any(previous_dir.glob("*.csv.gz")):
        previous_dir = None  # first release: nothing to compare with
    check = ReleaseCheck(compared=previous_dir is not None)
    for name in PUBLIC_QUERIES:
        current = _rows_in(current_dir, name)
        previous = _rows_in(previous_dir, name)
        check.changes.append(DatasetChange(name, previous, current))
        if current is None:
            check.problems.append(f"{name}.csv.gz is missing")
        elif current == 0:
            check.problems.append(f"{name} is empty")
        elif name == MAIN_DATASET and previous and current < previous * min_ratio:
            check.problems.append(
                f"{name} fell from {previous:,} to {current:,} rows (more than "
                f"{1 - min_ratio:.0%}). Check the SERCOP downloads before publishing."
            )
    return check


def to_markdown(check: ReleaseCheck) -> str:
    """A table for the GitHub Actions run page (``$GITHUB_STEP_SUMMARY``)."""

    def show(value: int | None) -> str:
        return "—" if value is None else f"{value:,}"

    lines = [
        "## Revisión antes de publicar",
        "",
        "| Dataset | Antes | Ahora | Cambio |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| {c.name} | {show(c.previous)} | {show(c.current)} | {c.change} |" for c in check.changes
    ]
    lines.append("")
    if not check.compared:
        lines.append("No hay una publicación anterior para comparar.")
    if check.ok:
        lines.append("✅ Todo bien: se puede publicar.")
    else:
        lines.append("❌ No se publica:")
        lines += [f"- {problem}" for problem in check.problems]
    return "\n".join(lines) + "\n"
