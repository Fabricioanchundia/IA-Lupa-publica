"""Questions about procurement law, answered from the law itself (Phase 8b: RAG).

RAG = Retrieval-Augmented Generation. Instead of trusting what a model "remembers"
about Ecuadorian law, we:
1. split the official texts (LOSNCP and its General Regulation) into articles;
2. turn every article into an embedding, a list of numbers that captures its meaning
   (Ollama model bge-m3, multilingual);
3. for a question, find the articles whose meaning is closest (cosine similarity);
4. give ONLY those articles to the model and ask it to answer citing them;
5. check that every citation in the answer is one of the articles it was given.

Everything runs locally and costs nothing. It is not legal advice.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import duckdb
import httpx

from lupa_publica.llm import DEFAULT_URL, LanguageModel, Message

DEFAULT_EMBED_MODEL = "bge-m3"
# A general model cites better than a coding model (compared on the same questions:
# qwen2.5-coder answered without citations, qwen2.5 cited the article).
DEFAULT_LAW_MODEL = "qwen2.5:7b"
MAX_CHARS = 1500  # long articles are split into parts of about this size
TOP_K = 8

# Article headings: "Art. 6.-", "Artículo 6.-", "Art. 45 bis.-", "Art. 6.1.-", "Art. (...).-".
# The dash after the number is required, so a reference inside a sentence ("el Art. 6 de
# esta Ley") is not taken for a new article. Headings are found anywhere, not only at the
# start of a line, because PDF extraction often joins lines.
DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
ARTICLE = re.compile(
    r"(?<![\w])Art(?:[íi]culo|\.)\s*"
    r"(?P<num>\d+(?:\.\d+)*(?:\s*(?:bis|ter|quater|quinquies))?|innumerado|\(\.\.\.\))"
    rf"\s*(?:\.\s*)?[{DASHES}]+\s*",
    flags=re.IGNORECASE,
)
# Any mention of an article in an answer: [LOSNCP Art. 6], (Art. 6), artículo 6 ...
MENTION = re.compile(
    r"\b(?:art[íi]culo|art\.)\s*(?P<num>\d+(?:\.\d+)*(?:\s*(?:bis|ter|quater))?)",
    flags=re.IGNORECASE,
)
PAGE_NUMBER = re.compile(r"^\s*(?:P[áa]g(?:ina)?\.?\s*)?\d+\s*(?:de\s*\d+)?\s*$", re.IGNORECASE)
CITATION = re.compile(r"\[(?P<source>[A-ZÁÉÍÓÚ]+)\s*Art\.?\s*(?P<num>[^\]]+?)\]", re.IGNORECASE)
# The article inside a citation. Anything after it is a paragraph or item of the same
# article ("[RGLOSNCP Art. 258, 1]", "[LOSNCP Art. 6 numeral 3]") and is accepted.
ARTICLE_NUMBER = re.compile(
    r"\d+(?:\.\d+)*(?:\s*(?:bis|ter|quater|quinquies))?|innumerado(?:-\d+)?", re.IGNORECASE
)


def cited_articles(text: str) -> list[tuple[str, str]]:
    """(source, article) of every [SOURCE Art. N] citation in ``text``."""
    found: list[tuple[str, str]] = []
    for match in CITATION.finditer(text):
        number = ARTICLE_NUMBER.match(match.group("num").strip())
        value = number.group(0) if number else match.group("num")
        found.append((match.group("source").upper(), " ".join(value.split()).lower()))
    return found


@dataclass(frozen=True)
class Article:
    source: str  # e.g. "LOSNCP"
    number: str  # e.g. "6", "45 bis", "innumerado-3"
    part: int
    text: str

    @property
    def citation(self) -> str:
        return f"[{self.source} Art. {self.number}]"


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text."""
        ...


class OllamaEmbedder:
    """Embeddings from Ollama's /api/embed (default model bge-m3)."""

    def __init__(
        self,
        model: str = DEFAULT_EMBED_MODEL,
        base_url: str = DEFAULT_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=300.0)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = self._client.post(
            f"{self.base_url}/api/embed", json={"model": self.model, "input": list(texts)}
        )
        if response.status_code == 404:
            raise RuntimeError(f"model '{self.model}' not found: ollama pull {self.model}")
        response.raise_for_status()
        return [[float(x) for x in vector] for vector in response.json()["embeddings"]]


# ---------------------------------------------------------------- reading the PDFs


Mode = Literal["plain", "layout"]


def pdf_pages(path: Path, mode: Mode = "plain") -> list[str]:
    from pypdf import PdfReader  # only indexing needs it

    return [page.extract_text(extraction_mode=mode) or "" for page in PdfReader(path).pages]


# In some PDFs the bold heading "Art. 1" is extracted AFTER the first line of the article:
# ".- Objeto y ámbito.- El objeto de la presente Ley ... Art. 1". Put it back in front.
TRAILING_HEADING = re.compile(
    r"^(?P<body>\.\s*[-\u2010-\u2015\u2212].*?)\s*"
    r"(?P<head>Art(?:[íi]culo|\.)\s*(?:\d+(?:\.\d+)*(?:\s*(?:bis|ter|quater|quinquies))?"
    r"|\(\.\.\.\)))\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)


def restore_headings(text: str) -> str:
    return TRAILING_HEADING.sub(lambda m: f"{m.group('head')}{m.group('body')}", text)


def extract_articles(path: Path, source: str) -> tuple[list[Article], Mode]:
    """Split a PDF into articles, trying two ways of reading it; keep the better one.

    "layout" keeps the text in its visual order; "plain" is faster but can move bold
    headings around (fixed by restore_headings). Returns the articles and the mode used.
    """
    best: tuple[list[Article], Mode] = ([], "plain")
    modes: tuple[Mode, ...] = ("layout", "plain")
    for mode in modes:
        text = restore_headings(clean_pages(pdf_pages(path, mode)))
        articles = split_articles(text, source)
        if len({a.number for a in articles}) > len({a.number for a in best[0]}):
            best = (articles, mode)
    return best


def clean_pages(pages: Sequence[str]) -> str:
    """Join pages, dropping page numbers and running headers/footers.

    A line that repeats on many pages (the law's title, a publisher's footer) is not
    part of any article.
    """
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update({line.strip() for line in page.splitlines() if line.strip()})
    repeated = {line for line, n in counts.items() if n >= max(3, len(pages) // 4)}
    kept: list[str] = []
    for page in pages:
        for line in page.splitlines():
            text = line.strip()
            if not text or text in repeated or PAGE_NUMBER.match(text):
                continue
            kept.append(text)
    return "\n".join(kept)


def split_articles(text: str, source: str, max_chars: int = MAX_CHARS) -> list[Article]:
    """Cut the law into articles (and long articles into parts)."""
    # NFKC turns look-alike characters (non-breaking spaces, ligatures) into plain ones.
    text = unicodedata.normalize("NFKC", text)
    matches = list(ARTICLE.finditer(text))
    articles: list[Article] = []
    seen: Counter[str] = Counter()
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = " ".join(text[match.start() : end].split())
        number = " ".join(match.group("num").split()).lower()
        if number in {"innumerado", "(...)"}:
            number = "innumerado"
        seen[number] += 1
        if seen[number] > 1:
            # Reforms add unnumbered articles, and some texts repeat a number: keep
            # each one, distinguishable.
            number = f"{number}-{seen[number]}"
        for part, chunk in enumerate(_parts(body, max_chars), start=1):
            articles.append(Article(source, number, part, chunk))
    return articles


def _parts(text: str, max_chars: int) -> Iterable[str]:
    if len(text) <= max_chars:
        yield text
        return
    sentences = re.split(r"(?<=[.;:])\s+", text)
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            yield current
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        yield current


# ---------------------------------------------------------------- the index


def build_index(
    db_path: Path, sources: dict[str, Path], embedder: Embedder, batch: int = 16
) -> dict[str, int]:
    """Read each PDF, split it into articles, embed them and store them in DuckDB."""
    rows: list[tuple[str, str, int, str, list[float]]] = []
    counts: dict[str, int] = {}
    for source, path in sources.items():
        articles, _ = extract_articles(path, source)
        if not articles:
            raise ValueError(f"no articles found in {path}. Run: uv run lupa law-index --check")
        counts[source] = len({a.number for a in articles})
        for start in range(0, len(articles), batch):
            group = articles[start : start + batch]
            vectors = embedder.embed([f"{a.source} artículo {a.number}: {a.text}" for a in group])
            rows += [
                (a.source, a.number, a.part, a.text, v) for a, v in zip(group, vectors, strict=True)
            ]
    write_index(db_path, rows)
    return counts


def write_index(db_path: Path, rows: Sequence[tuple[str, str, int, str, list[float]]]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            "create or replace table law_chunks (source varchar, article varchar, "
            "part integer, text varchar, embedding float[])"
        )
        if rows:
            con.executemany("insert into law_chunks values (?, ?, ?, ?, ?)", list(rows))


@dataclass
class LawIndex:
    con: duckdb.DuckDBPyConnection
    embedder: Embedder

    @classmethod
    def open(cls, db_path: Path, embedder: Embedder) -> LawIndex:
        if not db_path.exists():
            raise FileNotFoundError(f"{db_path} not found. Run: uv run lupa law-index")
        con = duckdb.connect(str(db_path), read_only=True)
        counted = con.execute("select count(*) from law_chunks").fetchone()
        if not counted or counted[0] == 0:
            con.close()
            raise FileNotFoundError(f"{db_path} is empty. Run: uv run lupa law-index")
        return cls(con, embedder)

    def whole_articles(self, hits: Sequence[Article], max_chars: int) -> list[Article]:
        """The full text of each hit's article (all parts), in hit order, within a budget."""
        result: list[Article] = []
        used = 0
        for hit in hits:
            if any(a.source == hit.source and a.number == hit.number for a in result):
                continue
            rows = self.con.execute(
                "select text from law_chunks where source = ? and article = ? order by part",
                [hit.source, hit.number],
            ).fetchall()
            text = " ".join(str(r[0]) for r in rows)
            if result and used + len(text) > max_chars:
                continue
            result.append(Article(hit.source, hit.number, 0, text))
            used += len(text)
        return result

    def search(self, question: str, k: int = TOP_K) -> list[tuple[Article, float]]:
        """The k chunks closest in meaning, plus any article the question names."""
        (vector,) = self.embedder.embed([question])
        found = self.con.execute(
            "select source, article, part, text, "
            "list_cosine_similarity(embedding, ?::float[]) as score "
            "from law_chunks order by score desc limit ?",
            [vector, k],
        ).fetchall()
        named = re.findall(r"art[íi]culo\s+(\d+)|art\.\s*(\d+)", question, flags=re.IGNORECASE)
        numbers = {a or b for a, b in named}
        if numbers:
            found += self.con.execute(
                "select source, article, part, text, 1.0 from law_chunks "
                "where article in (select unnest(?::varchar[])) order by source, part",
                [sorted(numbers)],
            ).fetchall()
        results: dict[tuple[str, str, int], tuple[Article, float]] = {}
        for source, article, part, text, score in found:
            key = (source, article, part)
            if key not in results:
                results[key] = (Article(source, article, part, text), float(score))
        return list(results.values())


# ---------------------------------------------------------------- answering

ANSWER_RULES = """\
You answer questions about Ecuador's public procurement law in simple Spanish, for people
who are not lawyers.
- Use ONLY the articles given below. Never use outside knowledge, even if you think you
  know the answer: laws change, and only these texts are current.
- EVERY sentence must end with the citation of the article it comes from, written exactly
  as in the list, e.g. "El plazo es de cinco días [LOSNCP Art. 6]." A sentence you cannot
  cite must not be written.
- Copy numbers (amounts, days, percentages) exactly as the article says them.
- Copy each citation exactly as given, source included: LOSNCP is the Law and RGLOSNCP is
  its Regulation, and the same number can exist in both. Never change an article's source.
- If the articles do not answer the question, reply exactly:
  "No encontré la respuesta en los artículos consultados."
- 2 to 6 sentences.
"""
MAX_CONTEXT_CHARS = 16000
SOURCE_NAMES = {
    "LOSNCP": "Ley Orgánica del Sistema Nacional de Contratación Pública",
    "RGLOSNCP": "Reglamento General a la LOSNCP",
}


@dataclass
class LawAnswer:
    question: str
    text: str
    sources: list[Article] = field(default_factory=list)
    unverified_citations: list[str] = field(default_factory=list)


NOT_FOUND = "No encontré la respuesta en los artículos consultados."


def verify_citations(text: str, sources: Sequence[Article]) -> list[str]:
    """Article references in ``text`` that are not among the given articles.

    Checks the exact format [LOSNCP Art. 6] and also any loose mention ("artículo 10",
    "(LOSNCP Art. 10)"), because a model that ignores the format may also ignore the
    sources. An answer with no citation at all is flagged too, unless it says that the
    articles do not answer the question.
    """
    given = {(a.source.upper(), a.number.lower()) for a in sources}
    numbers = {a.number.lower() for a in sources}
    wrong: list[str] = []
    for match, key in zip(CITATION.finditer(text), cited_articles(text), strict=True):
        if key not in given:
            wrong.append(match.group(0))
    for match in MENTION.finditer(CITATION.sub("", text)):
        if " ".join(match.group("num").split()).lower() not in numbers:
            wrong.append(match.group(0))
    if not CITATION.search(text) and NOT_FOUND.lower() not in text.lower():
        wrong.append("(sin citas)")
    return wrong


def answer(question: str, index: LawIndex, model: LanguageModel) -> LawAnswer:
    hits = index.search(question)
    if not hits:
        # Never let the model answer a legal question from memory.
        return LawAnswer(question, NOT_FOUND)
    # A hit is often one part of a long article; give the model the whole article, so a
    # rule split across parts (a deadline in the second paragraph) is not lost.
    articles = index.whole_articles([article for article, _ in hits], MAX_CONTEXT_CHARS)
    context = "\n\n".join(
        f"{a.citation} ({SOURCE_NAMES.get(a.source, a.source)})\n{a.text}" for a in articles
    )
    reply = model.complete(
        [
            Message("system", ANSWER_RULES),
            Message("user", f"Articles:\n{context}\n\nQuestion: {question}"),
        ]
    ).strip()
    return LawAnswer(question, reply, articles, verify_citations(reply, articles))


def heading_samples(text: str, limit: int = 5) -> list[str]:
    """Lines that mention 'Art' as extracted, to see why headings were not recognised."""
    return [repr(line[:80]) for line in text.splitlines() if "art" in line.lower()][:limit]


def numbering_report(articles: Sequence[Article]) -> dict[str, object]:
    """Quick check that the PDF was split well: how many articles, and gaps in numbering.

    Numbers that should exist but were not found usually mean a heading the splitter did
    not recognise (or articles repealed by a reform).
    """
    numbers = sorted({int(a.number) for a in articles if a.number.isdigit()})
    missing = [n for n in range(1, numbers[-1] + 1) if n not in set(numbers)] if numbers else []
    return {
        "articles": len({a.number for a in articles}),
        "chunks": len(articles),
        "first": [a.citation for a in articles[:3]],
        "last": [a.citation for a in articles[-3:]],
        "missing_numbers": missing,
    }
