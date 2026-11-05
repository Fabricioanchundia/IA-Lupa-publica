"""Answered example questions for the website (free alternative to a hosted model).

A public "ask anything" box would need a model running on a server for every visitor,
which costs money. Instead, the questions in a text file are answered on the
developer's computer with the local model, a person reviews them, and the website
shows them with their SQL and table; visitors can re-run each SQL in their own
browser to check it. Results come only from the public datasets, and the file is
scanned for personal identifiers before it is written, like the public export.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from lupa_publica.ask import Answer, ask
from lupa_publica.export import FULL_PSEUDONYM, PERSON_RUC, PublicDataError
from lupa_publica.llm import LanguageModel

MAX_ROWS = 20


def read_questions(path: Path) -> list[str]:
    """One question per line; blank lines and lines starting with # are skipped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def to_json_value(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return round(value, 2)
    return str(value)


def example(answer: Answer) -> dict[str, object]:
    return {
        "question": answer.question,
        "refusal": answer.refusal,
        "sql": answer.sql,
        "columns": answer.columns,
        "rows": [[to_json_value(v) for v in row] for row in answer.rows[:MAX_ROWS]],
        "row_count": len(answer.rows),
        "explanation": answer.explanation,
        "unverified_numbers": answer.unverified_numbers,
    }


@dataclass
class GalleryReport:
    answered: int = 0
    refused: int = 0
    failed: list[str] = field(default_factory=list)


def build_gallery(
    questions: Sequence[str],
    model: LanguageModel,
    con: duckdb.DuckDBPyConnection,
    model_name: str,
    progress: Callable[[int, int, str], None] | None = None,
) -> tuple[dict[str, object], GalleryReport]:
    """Answer every question. Failed ones are reported, not published."""
    report = GalleryReport()
    examples: list[dict[str, object]] = []
    for number, question in enumerate(questions, start=1):
        if progress:
            progress(number, len(questions), question)
        answer = ask(question, model, con)
        if answer.refusal is not None:
            report.refused += 1
        elif answer.ok:
            report.answered += 1
        else:
            report.failed.append(f"{question} -> {answer.error}")
            continue
        examples.append(example(answer))
    gallery: dict[str, object] = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "model": model_name,
        "examples": examples,
    }
    return gallery, report


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def write_gallery(gallery: dict[str, object], path: Path) -> None:
    """Write the gallery JSON, refusing if any text looks like personal data."""
    for text in _strings(gallery):
        if PERSON_RUC.search(text) or FULL_PSEUDONYM.search(text):
            raise PublicDataError(f"personal identifier found in the gallery: {text[:60]}...")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gallery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
