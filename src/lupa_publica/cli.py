"""Command-line interface: ``lupa ingest``, ``backfill``, ``report``, ``export-public``, ``ask``."""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import httpx

from lupa_publica.ask import Answer, ask, open_public_data, show
from lupa_publica.ask_gallery import build_gallery, read_questions, write_gallery
from lupa_publica.export import PublicDataError, export_public
from lupa_publica.extract import Month
from lupa_publica.llm import LLMError, OllamaModel
from lupa_publica.lock import AlreadyRunningError, exclusive_lock
from lupa_publica.pipeline import DataPaths, IngestResult, ingest, last_months, month_range
from lupa_publica.privacy import MissingKeyError
from lupa_publica.report import build_report, render_markdown


def parse_month(text: str) -> Month:
    """Parse ``YYYY-MM`` into a Month (used by argparse)."""
    try:
        year, month = (int(part) for part in text.split("-"))
        return Month(year, month)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM, got {text!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lupa", description="Lupa Pública data pipeline")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="default: data")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    commands = parser.add_subparsers(dest="command", required=True)

    ingest_cmd = commands.add_parser(
        "ingest", help="refresh the most recent months (rolling window, re-downloads)"
    )
    ingest_cmd.add_argument("--months", type=int, default=6, help="window size (default: 6)")

    backfill_cmd = commands.add_parser(
        "backfill", help="load a historical range, skipping files already downloaded"
    )
    backfill_cmd.add_argument("--from", dest="start", type=parse_month, required=True)
    backfill_cmd.add_argument("--to", dest="end", type=parse_month, required=True)

    report_cmd = commands.add_parser("report", help="data coverage report in Markdown")
    report_cmd.add_argument(
        "--output", type=Path, help="write the report to this file instead of printing it"
    )
    export_cmd = commands.add_parser(
        "export-public", help="write the public datasets for the website (allowlist)"
    )
    export_cmd.add_argument("--output", type=Path, help="output folder (default: web/public/data)")

    ask_cmd = commands.add_parser("ask", help="ask a question in Spanish about the public data")
    ask_cmd.add_argument("question", help='e.g. "¿Qué entidades hay que revisar primero?"')
    ask_cmd.add_argument(
        "--public-data",
        type=Path,
        default=Path("web/public/data"),
        help="folder written by export-public (default: web/public/data)",
    )
    ask_cmd.add_argument("--model", help="Ollama model (default: $LUPA_LLM_MODEL or qwen2.5:7b)")
    ask_cmd.add_argument("--no-explain", action="store_true", help="only the SQL and the table")

    gallery_cmd = commands.add_parser(
        "ask-examples", help="answer a list of questions for the website's AI gallery"
    )
    gallery_cmd.add_argument(
        "--questions",
        type=Path,
        default=Path("web/ask-examples.txt"),
        help="one question per line (default: web/ask-examples.txt)",
    )
    gallery_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("web/src/askExamples.json"),
        help="default: web/src/askExamples.json",
    )
    gallery_cmd.add_argument("--public-data", type=Path, default=Path("web/public/data"))
    gallery_cmd.add_argument("--model", help="Ollama model (default: qwen2.5:7b)")

    mcp_cmd = commands.add_parser(
        "mcp", help="MCP server over stdio so AI assistants can query the public data"
    )
    mcp_cmd.add_argument("--public-data", type=Path, default=Path("web/public/data"))
    mcp_cmd.add_argument("--law-index", type=Path, default=Path("data/law/law.duckdb"))

    law_index_cmd = commands.add_parser(
        "law-index", help="split the law PDFs into articles and embed them (RAG index)"
    )
    law_index_cmd.add_argument(
        "--pdf",
        action="append",
        metavar="NAME=PATH",
        help="default: LOSNCP=data/law/LOSNCP.pdf and RGLOSNCP=data/law/RGLOSNCP.pdf",
    )
    law_index_cmd.add_argument("--index", type=Path, default=Path("data/law/law.duckdb"))
    law_index_cmd.add_argument(
        "--check", action="store_true", help="only show how the PDFs split, do not embed"
    )

    law_cmd = commands.add_parser("law", help="ask about procurement law, with cited articles")
    law_cmd.add_argument("question")
    law_cmd.add_argument("--index", type=Path, default=Path("data/law/law.duckdb"))
    law_cmd.add_argument("--model", help="Ollama model (default: $LUPA_LAW_MODEL or qwen2.5:7b)")

    eval_cmd = commands.add_parser("eval", help="grade the AI on a fixed question set")
    eval_cmd.add_argument("kind", choices=["ask", "law"], help="what to evaluate")
    eval_cmd.add_argument("--cases", type=Path, help="default: evals/<kind>.toml")
    eval_cmd.add_argument("--model", help="Ollama model to grade")
    eval_cmd.add_argument("--limit", type=int, help="only the first N cases (quick check)")
    eval_cmd.add_argument("--out", type=Path, default=Path("evals/results"))
    eval_cmd.add_argument("--public-data", type=Path, default=Path("web/public/data"))
    eval_cmd.add_argument("--index", type=Path, default=Path("data/law/law.duckdb"))
    eval_cmd.add_argument("--no-explain", action="store_true", help="ask: skip explanations")
    return parser


def run_export(paths: DataPaths, output: Path | None) -> int:
    out_dir = output or Path("web/public/data")
    try:
        report = export_public(paths.db, out_dir)
    except (PublicDataError, MissingKeyError) as exc:
        print(f"export refused: {exc}")
        return 1
    for name, rows in report.rows.items():
        print(f"{name:<20} {rows:>8,} rows")
    print(f"public datasets written to {out_dir}")
    return 0


def print_summary(result: IngestResult) -> None:
    print(f"\n{'month':<8} {'processes':>10} {'rejected':>9} {'duplicates':>11}")
    for report in result.months:
        print(
            f"{report.month:<8} {report.written:>10,} {report.rejected:>9,} "
            f"{report.duplicates:>11,}"
        )
    for label, error in result.failures.items():
        print(f"{label:<8} FAILED: {error}")
    if result.load is not None:
        print(
            f"\nbronze.releases: {result.load.rows:,} processes "
            f"from {result.load.files} monthly files"
        )
    print("status:", "OK" if result.ok else "FAILED")


def run_report(paths: DataPaths, output: Path | None) -> int:
    text = render_markdown(build_report(paths.db))
    if output is None:
        print(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"report written to {output}")
    return 0


def print_answer(answer: Answer, max_rows: int = 20) -> None:
    if answer.refusal:
        print(f"No se puede responder: {answer.refusal}")
        return
    if not answer.ok:
        print(f"No pude escribir una consulta válida ({answer.attempts} intentos): {answer.error}")
        return
    print(f"SQL ({answer.attempts} intento{'s' if answer.attempts > 1 else ''}):\n{answer.sql}\n")
    widths = [
        max([len(c)] + [len(show(r[i])) for r in answer.rows[:max_rows]])
        for i, c in enumerate(answer.columns)
    ]
    print("  ".join(c.ljust(w) for c, w in zip(answer.columns, widths, strict=True)))
    for row in answer.rows[:max_rows]:
        print("  ".join(show(v).ljust(w) for v, w in zip(row, widths, strict=True)))
    if len(answer.rows) > max_rows:
        print(f"... {len(answer.rows) - max_rows} filas más")
    if answer.explanation:
        print(f"\n{answer.explanation}")
        print("\n(Explicación escrita por IA: la tabla de arriba es el dato exacto.)")
    if answer.unverified_numbers:
        print(
            "⚠️  La explicación menciona números que no están en la tabla: "
            + ", ".join(answer.unverified_numbers)
            + ". Confía en la tabla."
        )


def run_ask(question: str, data_dir: Path, model_name: str | None, explain: bool) -> int:
    try:
        con = open_public_data(data_dir)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    try:
        answer = ask(question, OllamaModel(model=model_name), con, explain=explain)
    except LLMError as exc:
        print(f"AI not available: {exc}")
        return 1
    finally:
        con.close()
    print_answer(answer)
    return 0 if answer.ok or answer.refusal else 1


def run_gallery(questions_file: Path, output: Path, data_dir: Path, model_name: str | None) -> int:
    try:
        questions = read_questions(questions_file)
        con = open_public_data(data_dir)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    model = OllamaModel(model=model_name)
    try:
        gallery, report = build_gallery(
            questions,
            model,
            con,
            model.model,
            progress=lambda n, total, q: print(f"[{n}/{total}] {q}", flush=True),
        )
    except LLMError as exc:
        print(f"AI not available: {exc}")
        return 1
    finally:
        con.close()
    try:
        write_gallery(gallery, output)
    except PublicDataError as exc:
        print(f"gallery refused: {exc}")
        return 1
    print(f"\n{report.answered} answered, {report.refused} declined, {len(report.failed)} failed")
    for failure in report.failed:
        print(f"  FAILED (not published): {failure}")
    print(f"written to {output}. Review every answer before you commit it.")
    return 0


def law_sources(pairs: list[str] | None) -> dict[str, Path]:
    if not pairs:
        return {name: Path("data/law") / f"{name}.pdf" for name in ("LOSNCP", "RGLOSNCP")}
    sources: dict[str, Path] = {}
    for pair in pairs:
        name, _, path = pair.partition("=")
        sources[name.strip().upper()] = Path(path)
    return sources


def run_law_index(pairs: list[str] | None, index: Path, check: bool) -> int:
    from lupa_publica import law

    sources = law_sources(pairs)
    missing = [str(p) for p in sources.values() if not p.exists()]
    if missing:
        print(f"PDF not found: {', '.join(missing)}")
        return 1
    if check:
        for name, path in sources.items():
            articles, mode = law.extract_articles(path, name)
            report = law.numbering_report(articles)
            text = law.clean_pages(law.pdf_pages(path, mode))
            print(f"\n{name}: {len(text):,} characters of text (read in '{mode}' mode)")
            print(f"  {report['articles']} articles in {report['chunks']} chunks")
            print(f"  first: {report['first']}\n  last:  {report['last']}")
            print(f"  numbers not found: {report['missing_numbers'] or 'none'}")
            if not articles:
                print("  lines with 'art' as extracted:")
                for sample in law.heading_samples(text):
                    print(f"    {sample}")
        return 0
    try:
        counts = law.build_index(index, sources, law.OllamaEmbedder())
    except ValueError as exc:
        print(f"index not written: {exc}")
        return 1
    except (RuntimeError, httpx.HTTPError) as exc:
        print(f"AI not available: {exc}")
        return 1
    for name, count in counts.items():
        print(f"{name}: {count} articles indexed")
    print(f"index written to {index}")
    return 0


def run_law(question: str, index: Path, model_name: str | None) -> int:
    from lupa_publica import law

    try:
        law_index = law.LawIndex.open(index, law.OllamaEmbedder())
        model = OllamaModel(
            model=model_name or os.environ.get("LUPA_LAW_MODEL", law.DEFAULT_LAW_MODEL)
        )
        result = law.answer(question, law_index, model)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    except (LLMError, RuntimeError, httpx.HTTPError) as exc:
        print(f"AI not available: {exc}")
        return 1
    print(result.text)
    if "(sin citas)" in result.unverified_citations:
        print(
            "\n⚠️  La respuesta NO cita ningún artículo: puede venir de la memoria de la IA. "
            "No la uses sin leer los artículos de abajo."
        )
    wrong = [c for c in result.unverified_citations if c != "(sin citas)"]
    if wrong:
        print("\n⚠️  Citas que NO están entre los artículos consultados: " + ", ".join(wrong))
    print("\nArtículos consultados (texto completo enviado a la IA):")
    for article in result.sources:
        print(f"  {article.citation} {article.text[:110]}…")
    print("\nRespuesta escrita por IA a partir del texto oficial. No es asesoría legal.")
    return 0


def run_eval(args: argparse.Namespace) -> int:
    from lupa_publica import evaluate, law

    cases = evaluate.load_cases(args.cases or Path("evals") / f"{args.kind}.toml")
    if args.limit:
        cases = cases[: args.limit]

    def progress(n: int, total: int, question: str) -> None:
        print(f"[{n}/{total}] {question}", flush=True)

    try:
        if args.kind == "ask":
            model = OllamaModel(model=args.model)
            con = open_public_data(args.public_data)
            try:
                results = evaluate.run_ask_eval(
                    cases, model, con, explain=not args.no_explain, progress=progress
                )
            finally:
                con.close()
            summary = evaluate.ask_summary(cases, results)
        else:
            model = OllamaModel(
                model=args.model or os.environ.get("LUPA_LAW_MODEL", law.DEFAULT_LAW_MODEL)
            )
            index = law.LawIndex.open(args.index, law.OllamaEmbedder())
            results = evaluate.run_law_eval(cases, index, model, progress=progress)
            summary = evaluate.law_summary(cases, results)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    except (LLMError, RuntimeError, httpx.HTTPError) as exc:
        print(f"AI not available: {exc}")
        return 1

    print()
    for r in results:
        print(f"{'✅' if r.passed else '❌'} {r.id:<28} {r.reason[:90]}")
    print()
    for key, value in summary.items():
        print(f"{key:<38} {value}")
    json_path, md_path = evaluate.write_report(args.kind, model.model, summary, results, args.out)
    print(f"\nreport: {md_path} (all details in {json_path.name})")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    paths = DataPaths(args.data_dir)

    if args.command == "report":
        return run_report(paths, args.output)
    if args.command == "export-public":
        return run_export(paths, args.output)
    if args.command == "ask":
        return run_ask(args.question, args.public_data, args.model, not args.no_explain)
    if args.command == "ask-examples":
        return run_gallery(args.questions, args.output, args.public_data, args.model)
    if args.command == "mcp":
        # Imported here: only this command needs the MCP library.
        from lupa_publica.mcp_server import serve

        serve(args.public_data, args.law_index)
        return 0
    if args.command == "law-index":
        return run_law_index(args.pdf, args.index, args.check)
    if args.command == "law":
        return run_law(args.question, args.index, args.model)
    if args.command == "eval":
        return run_eval(args)

    if args.command == "ingest":
        if args.months < 1:
            parser.error("--months must be at least 1")
        months = last_months(args.months, date.today())
        refresh = True
    else:
        try:
            months = month_range(args.start, args.end)
        except ValueError as exc:
            parser.error(str(exc))
        refresh = False

    try:
        with exclusive_lock(paths.lock):
            result = ingest(months, paths, refresh=refresh)
    except AlreadyRunningError as exc:
        print(f"{exc}. Wait for it to finish, or stop it before starting a new one.")
        return 1
    print_summary(result)
    return 0 if result.ok else 1
