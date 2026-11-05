import asyncio
import math
import re
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest
from test_ask import FakeModel
from test_export import make_gold

from lupa_publica import law
from lupa_publica.ask import open_public_data
from lupa_publica.export import export_public
from lupa_publica.law import (
    Article,
    LawIndex,
    OllamaEmbedder,
    answer,
    build_index,
    clean_pages,
    numbering_report,
    split_articles,
    verify_citations,
)
from lupa_publica.mcp_server import build_server

LAW_TEXT = """\
Art. 1.- Objeto y ámbito.- Esta Ley determina los principios del Sistema Nacional de
Contratación Pública para la adquisición de bienes, obras y servicios. Se aplica a las
entidades señaladas en el
Art. 6 de esta Ley y a las demás del sector público.
Art. 6.- Definiciones.- Subasta inversa: procedimiento en el que los proveedores pujan
hacia la baja el precio ofertado, en acto público o por medios electrónicos.
Art. (...).- Integridad.- Las entidades publicarán sus procesos en el portal.
Art. 45 bis.- Plazo para ofertar.- El plazo para presentar ofertas no será menor de
cinco días en los procedimientos de subasta inversa electrónica.
"""


class WordEmbedder:
    """Deterministic fake embeddings: a vector of word counts over a small vocabulary."""

    VOCAB = ["subasta", "plazo", "ofertas", "días", "portal", "publicarán", "objeto", "ley"]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            words = re.findall(r"\w+", text.lower())
            vectors.append([float(words.count(v)) + 0.01 for v in self.VOCAB])
        return vectors


def test_splits_on_article_headings_only() -> None:
    articles = split_articles(LAW_TEXT, "LOSNCP")
    assert [a.number for a in articles] == ["1", "6", "innumerado", "45 bis"]
    # "Art. 6 de esta Ley" inside article 1 did not start a new article.
    assert "Art. 6 de esta Ley" in articles[0].text
    assert articles[3].citation == "[LOSNCP Art. 45 bis]"


def test_long_articles_are_split_into_parts() -> None:
    long_text = "Art. 9.- Largo.- " + "Una oración de prueba bastante larga. " * 100
    parts = split_articles(long_text, "LOSNCP", max_chars=500)
    assert len(parts) > 3
    assert {p.number for p in parts} == {"9"}
    assert [p.part for p in parts] == list(range(1, len(parts) + 1))
    assert all(len(p.text) <= 520 for p in parts)


def test_repeated_innumerado_articles_stay_distinct() -> None:
    text = "Art. (...).- Uno.\nArt. (...).- Dos.\n"
    assert [a.number for a in split_articles(text, "X")] == ["innumerado", "innumerado-2"]


def test_clean_pages_drops_headers_and_page_numbers() -> None:
    pages = [
        f"LEY ORGÁNICA DEL SISTEMA NACIONAL\nArt. {n}.- Texto {n}.\nPágina {n} de 4"
        for n in (1, 2, 3, 4)
    ]
    text = clean_pages(pages)
    assert "LEY ORGÁNICA DEL SISTEMA NACIONAL" not in text
    assert "Página" not in text
    assert "Art. 3.- Texto 3." in text


def test_numbering_report_shows_gaps() -> None:
    report = numbering_report(split_articles(LAW_TEXT, "LOSNCP"))
    assert report["articles"] == 4
    assert report["missing_numbers"] == [2, 3, 4, 5]


@pytest.fixture
def index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LawIndex:
    monkeypatch.setattr(law, "pdf_pages", lambda path, mode="plain": [LAW_TEXT])
    pdf = tmp_path / "LOSNCP.pdf"
    pdf.write_bytes(b"fake")
    counts = build_index(tmp_path / "law.duckdb", {"LOSNCP": pdf}, WordEmbedder())
    assert counts == {"LOSNCP": 4}
    return LawIndex.open(tmp_path / "law.duckdb", WordEmbedder())


def test_search_finds_the_closest_article(index: LawIndex) -> None:
    hits = index.search("¿Cuántos días de plazo para ofertas en una subasta?", k=1)
    assert hits[0][0].citation == "[LOSNCP Art. 45 bis]"
    assert -1.0 <= hits[0][1] <= 1.0 and not math.isnan(hits[0][1])


def test_search_adds_articles_named_in_the_question(index: LawIndex) -> None:
    hits = index.search("¿Qué dice el artículo 6?", k=1)
    assert "[LOSNCP Art. 6]" in {a.citation for a, _ in hits}


def test_answer_marks_citations_that_were_not_given(index: LawIndex) -> None:
    model = FakeModel(
        "El plazo no será menor de cinco días [LOSNCP Art. 45 bis]. "
        "También aplica el [LOSNCP Art. 99]."
    )

    result = answer("¿Cuál es el plazo para ofertar en una subasta?", index, model)

    assert result.unverified_citations == ["[LOSNCP Art. 99]"]
    prompt = model.calls[0][-1].content
    assert "[LOSNCP Art. 45 bis]" in prompt and "Question:" in prompt


def test_verify_citations_ignores_spacing_and_case() -> None:
    sources = [Article("LOSNCP", "45 bis", 1, "...")]
    assert verify_citations("ver [losncp art.  45 BIS]", sources) == []


def test_missing_index_says_how_to_build_it(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="lupa law-index"):
        LawIndex.open(tmp_path / "nope.duckdb", WordEmbedder())


def test_ollama_embedder_request() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    embedder = OllamaEmbedder(
        base_url="http://ollama.test", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert embedder.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert seen["url"] == "http://ollama.test/api/embed"
    assert '"bge-m3"' in seen["body"]


def test_mcp_offers_search_law_when_an_index_exists(index: LawIndex, tmp_path: Path) -> None:
    db = tmp_path / "lupa.duckdb"
    make_gold(db)
    export_public(db, tmp_path / "public")
    server = build_server(open_public_data(tmp_path / "public"), index)

    names = {t.name for t in asyncio.run(server.list_tools())}
    assert "search_law" in names
    result = asyncio.run(server.call_tool("search_law", {"question": "plazo subasta", "k": 1}))
    text = result.content[0].text
    assert text.startswith("[LOSNCP Art. 45 bis]")


def test_headings_with_other_dashes_and_joined_lines() -> None:
    # Real PDFs: a non-breaking hyphen after the number, and a heading glued to the
    # previous sentence because extraction joined two lines.
    text = "Art. 1.‑ Objeto.- Primero. Fin del uno. Art. 2.– Ámbito.- Segundo."
    assert [a.number for a in split_articles(text, "LOSNCP")] == ["1", "2"]


def test_a_pdf_without_articles_is_not_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        law, "pdf_pages", lambda path, mode="plain": ["Texto sin encabezados de artículos."]
    )
    with pytest.raises(ValueError, match="no articles found"):
        build_index(tmp_path / "law.duckdb", {"X": tmp_path / "x.pdf"}, WordEmbedder())
    assert not (tmp_path / "law.duckdb").exists()


def test_an_empty_index_is_refused(tmp_path: Path) -> None:
    law.write_index(tmp_path / "law.duckdb", [])
    with pytest.raises(FileNotFoundError, match="is empty"):
        LawIndex.open(tmp_path / "law.duckdb", WordEmbedder())


def test_without_articles_the_model_is_never_asked(
    index: LawIndex, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A real failure: with an empty index the model invented a "Decreto Supremo".
    monkeypatch.setattr(index, "search", lambda question, k=6: [])
    model = FakeModel()

    result = answer("¿Plazo de la subasta?", index, model)

    assert result.text == law.NOT_FOUND
    assert model.calls == []


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Está en el decreto (LOSNCP Art. 10).", ["Art. 10", "(sin citas)"]),
        ("Según el artículo 45 bis [LOSNCP Art. 45 bis], cinco días.", []),
        ("Son cinco días.", ["(sin citas)"]),
        (law.NOT_FOUND, []),
    ],
)
def test_loose_or_missing_citations_are_flagged(text: str, flagged: list[str]) -> None:
    sources = [Article("LOSNCP", "45 bis", 1, "...")]
    assert verify_citations(text, sources) == flagged


def test_headings_moved_to_the_end_of_the_line_are_put_back() -> None:
    # What pypdf's plain mode returned for the real LOSNCP.
    text = (
        ".- Objeto y ámbito material.- El objeto de la presente Ley es establecer Art. 1\n"
        "el Sistema Nacional de Contratación Pública.\n"
        ".- Ámbito territorial.- Las contrataciones que se realicen en el extranjero Art. 2\n"
        "se regirán por la ley del lugar.\n"
        "Artículo sustituido por artículo 1 de Ley No. 0, publicada en Registro Oficial.\n"
    )
    articles = split_articles(law.restore_headings(text), "LOSNCP")
    assert [a.number for a in articles] == ["1", "2"]
    assert articles[0].text.startswith("Art. 1.- Objeto y ámbito material.-")
    assert "Artículo sustituido" in articles[1].text


def test_extract_articles_keeps_the_better_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def pages(path: Path, mode: str = "plain") -> list[str]:
        if mode == "layout":
            return ["Texto sin encabezados."]
        return [".- Objeto.- Uno Art. 1\n.- Ámbito.- Dos Art. 2\n"]

    monkeypatch.setattr(law, "pdf_pages", pages)
    articles, mode = law.extract_articles(tmp_path / "x.pdf", "LOSNCP")
    assert mode == "plain"
    assert [a.number for a in articles] == ["1", "2"]


def test_the_model_gets_whole_articles_not_just_the_matching_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The deadline sits in the second part of a long article.
    long_article = (
        "Art. 9.- Subasta.- "
        + "Texto general de la subasta. " * 60
        + ("El plazo para ofertas será de cinco días.")
    )
    monkeypatch.setattr(law, "pdf_pages", lambda path, mode="plain": [long_article])
    build_index(tmp_path / "law.duckdb", {"LOSNCP": tmp_path / "x.pdf"}, WordEmbedder())
    index = LawIndex.open(tmp_path / "law.duckdb", WordEmbedder())
    model = FakeModel("Cinco días [LOSNCP Art. 9].")

    result = answer("subasta", index, model)

    assert len(result.sources) == 1
    assert "cinco días" in result.sources[0].text
    assert "cinco días" in model.calls[0][-1].content
