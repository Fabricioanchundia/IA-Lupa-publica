"""An exam for the AI, with a grade (Phase 9).

Saying "the AI works" is not enough: we measure it on fixed questions with known answers,
the same way every time, so models and prompts can be compared with numbers.

Text-to-SQL (`lupa ask`) is graded by **execution accuracy**, the usual metric in research
(Spider, BIRD): the model's SQL and a reference SQL written by a person are both run on
the public data, and the case passes if they return the same values. We also count
correct refusals, queries that never ran, and numbers in explanations that are not in
the result.

Law answers (`lupa law`) are graded on: did the search retrieve an expected article
(recall), does the answer cite it, are all citations real, and do the trap questions get
"No encontré...".
"""

from __future__ import annotations

import json
import time
import tomllib
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from lupa_publica.ask import PUBLIC_TABLES, ask, run_query
from lupa_publica.law import NOT_FOUND, LawIndex, cited_articles
from lupa_publica.law import answer as law_answer
from lupa_publica.llm import LanguageModel
from lupa_publica.sql_guard import check_sql

Progress = Callable[[int, int, str], None]


@dataclass
class CaseResult:
    id: str
    question: str
    passed: bool
    reason: str
    seconds: float
    details: dict[str, Any] = field(default_factory=dict)


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("rb") as file:
        cases = tomllib.load(file).get("case", [])
    ids = [c["id"] for c in cases]
    duplicated = [i for i, n in Counter(ids).items() if n > 1]
    if duplicated:
        raise ValueError(f"duplicated case ids: {duplicated}")
    return list(cases)


# ------------------------------------------------------------------ comparing results


def normalize(value: object) -> object:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return round(float(value), 2)
    return str(value).strip().upper()


def same_values(
    reference: tuple[list[str], list[tuple[object, ...]]],
    got: tuple[list[str], list[tuple[object, ...]]],
    ordered: bool = False,
) -> tuple[bool, str]:
    """Does ``got`` contain every column of ``reference`` with the same values?

    Column names, extra columns and (unless ``ordered``) row order do not matter.
    """
    ref_columns, ref_rows = reference
    got_columns, got_rows = got
    if len(ref_rows) != len(got_rows):
        return False, f"{len(got_rows)} rows, expected {len(ref_rows)}"
    candidates = [[normalize(row[j]) for row in got_rows] for j in range(len(got_columns))]
    for i, name in enumerate(ref_columns):
        expected = [normalize(row[i]) for row in ref_rows]
        if not any(_equal(expected, column, ordered) for column in candidates):
            sample = expected[:3]
            return False, f"no column matches the expected values of '{name}' {sample}"
    return True, "same values"


def _equal(expected: list[object], got: list[object], ordered: bool) -> bool:
    if ordered:
        return expected == got
    key = repr  # values of mixed types sort safely by their text
    return sorted(expected, key=key) == sorted(got, key=key)


# ------------------------------------------------------------------ Text-to-SQL


def run_ask_eval(
    cases: Sequence[dict[str, Any]],
    model: LanguageModel,
    con: duckdb.DuckDBPyConnection,
    explain: bool = True,
    progress: Progress | None = None,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for number, case in enumerate(cases, start=1):
        if progress:
            progress(number, len(cases), case["question"])
        start = time.perf_counter()
        answer = ask(case["question"], model, con, explain=explain)
        seconds = time.perf_counter() - start
        details: dict[str, Any] = {
            "sql": answer.sql,
            "attempts": answer.attempts,
            "unverified_numbers": answer.unverified_numbers,
        }
        if case.get("expect_refusal"):
            passed = not answer.ok
            if answer.refusal is not None:
                reason = "declined"
            elif answer.error is not None:
                reason = f"blocked: {answer.error[:80]}"
            else:
                reason = "answered a question it should have declined"
        elif not answer.ok:
            passed = False
            reason = (
                f"declined: {answer.refusal}" if answer.refusal else f"no valid SQL: {answer.error}"
            )
        else:
            reference = run_query(con, check_sql(case["reference_sql"], PUBLIC_TABLES))
            passed, reason = same_values(
                reference, (answer.columns, answer.rows), bool(case.get("ordered"))
            )
        results.append(CaseResult(case["id"], case["question"], passed, reason, seconds, details))
    return results


def ask_summary(cases: Sequence[dict[str, Any]], results: Sequence[CaseResult]) -> dict[str, Any]:
    by_id = {c["id"]: c for c in cases}
    answerable = [r for r in results if not by_id[r.id].get("expect_refusal")]
    refusals = [r for r in results if by_id[r.id].get("expect_refusal")]
    explained = [r for r in answerable if r.details.get("sql")]
    return {
        "cases": len(results),
        "execution_accuracy": _share([r.passed for r in answerable]),
        "correct": sum(r.passed for r in answerable),
        "answerable": len(answerable),
        "refusals_correct": sum(r.passed for r in refusals),
        "refusals": len(refusals),
        "no_valid_sql": sum(r.reason.startswith("no valid SQL") for r in answerable),
        "needed_second_try": sum(r.details.get("attempts", 1) > 1 for r in results),
        "explanations_with_unverified_numbers": sum(
            bool(r.details.get("unverified_numbers")) for r in explained
        ),
        "median_seconds": _median([r.seconds for r in results]),
    }


# ------------------------------------------------------------------ law (RAG)


def _cited(text: str, article: str) -> bool:
    source, _, number = article.partition(" ")
    return (source.upper(), number.lower()) in cited_articles(text)


def run_law_eval(
    cases: Sequence[dict[str, Any]],
    index: LawIndex,
    model: LanguageModel,
    progress: Progress | None = None,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for number, case in enumerate(cases, start=1):
        if progress:
            progress(number, len(cases), case["question"])
        start = time.perf_counter()
        result = law_answer(case["question"], index, model)
        seconds = time.perf_counter() - start
        sources = [f"{a.source} {a.number}" for a in result.sources]
        not_found = NOT_FOUND.lower() in result.text.lower()
        details: dict[str, Any] = {
            "answer": result.text,
            "retrieved": sources,
            "unverified_citations": result.unverified_citations,
        }
        if case.get("expect_not_found"):
            passed = not_found and not result.unverified_citations
            reason = (
                "said it did not find it"
                if passed
                else "answered a question the law does not cover"
            )
        else:
            expected = list(case["articles"])
            details["retrieved_expected"] = any(a in sources for a in expected)
            details["cited_expected"] = any(_cited(result.text, a) for a in expected)
            if not details["retrieved_expected"]:
                passed, reason = False, f"search did not find {expected}"
            elif not_found:
                passed, reason = False, "said not found, but the article was there"
            elif result.unverified_citations:
                passed, reason = False, f"unverified citations {result.unverified_citations}"
            elif not details["cited_expected"]:
                passed, reason = False, f"did not cite {expected}"
            else:
                passed, reason = True, "cited the expected article"
        results.append(CaseResult(case["id"], case["question"], passed, reason, seconds, details))
    return results


def law_summary(cases: Sequence[dict[str, Any]], results: Sequence[CaseResult]) -> dict[str, Any]:
    by_id = {c["id"]: c for c in cases}
    normal = [r for r in results if not by_id[r.id].get("expect_not_found")]
    traps = [r for r in results if by_id[r.id].get("expect_not_found")]
    return {
        "cases": len(results),
        "correct": sum(r.passed for r in normal),
        "answerable": len(normal),
        "accuracy": _share([r.passed for r in normal]),
        "retrieval_recall": _share([bool(r.details.get("retrieved_expected")) for r in normal]),
        "cited_expected": _share([bool(r.details.get("cited_expected")) for r in normal]),
        "answers_with_unverified_citations": sum(
            bool(r.details.get("unverified_citations")) for r in results
        ),
        "traps_correct": sum(r.passed for r in traps),
        "traps": len(traps),
        "median_seconds": _median([r.seconds for r in results]),
    }


# ------------------------------------------------------------------ reports


def _share(values: Sequence[bool]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    value = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return round(value, 1)


def write_report(
    kind: str,
    model: str,
    summary: dict[str, Any],
    results: Sequence[CaseResult],
    out_dir: Path,
) -> tuple[Path, Path]:
    """Save the run as JSON (every detail) and Markdown (to read and to link)."""
    now = datetime.now(UTC)
    stamp = now.strftime("%Y-%m-%d")
    # Date and time, so a second run on the same day does not overwrite the first.
    name = f"{kind}-{model.replace(':', '-').replace('/', '-')}-{now:%Y-%m-%d-%H%M}"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{name}.json"
    md_path = out_dir / f"{name}.md"
    payload = {
        "kind": kind,
        "model": model,
        "date": stamp,
        "summary": summary,
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [f"# Evaluation: {kind} with {model} ({stamp})", "", "| Metric | Value |", "|---|---|"]
    lines += [f"| {key} | {value} |" for key, value in summary.items()]
    lines += ["", "| Case | Result | Reason | Seconds |", "|---|---|---|---|"]
    for r in results:
        mark = "✅" if r.passed else "❌"
        reason = r.reason.replace("|", "/").replace("\n", " ")
        lines.append(f"| {r.id} | {mark} | {reason} | {r.seconds:.1f} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
