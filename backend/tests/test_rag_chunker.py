"""Task 4.1: the chunker splits by heading and never inside a fenced block (TEST-1)."""

from pathlib import Path

import pytest

from novamart_agent.errors import DataLoadError
from novamart_agent.models import Document
from novamart_agent.rag import chunk_document, chunk_documents, load_documents

FENCE = "`" * 3


def _doc(body: str, audience: str = "all_staff") -> Document:
    return Document("doc-a", "Doc A", "policy", audience, Path("doc-a.md"), body)


def test_fenced_diagram_stays_whole_in_one_chunk(data_dir: Path) -> None:
    documents = load_documents(data_dir / "docs")
    for document in documents:
        for chunk in chunk_document(document):
            assert chunk.text.count(FENCE) % 2 == 0, "a fence was split across chunks"
    fridge = next(d for d in documents if d.doc_id == "product-novacool-fridge")
    holding = [c for c in chunk_document(fridge) if "15 cm" in c.text]
    assert len(holding) == 1
    assert "10 cm" in holding[0].text and holding[0].text.count(FENCE) == 2


def test_hash_line_inside_a_fence_is_not_a_heading() -> None:
    lines = ["## One", "", "text", FENCE, "# not a heading", "line", FENCE, "## Two", "", "more"]
    chunks = chunk_document(_doc("\n".join(lines)))
    assert [c.heading for c in chunks] == ["One", "Two"]
    assert "# not a heading" in chunks[0].text


def test_chunk_carries_document_metadata() -> None:
    body = "\n".join(["# Doc A", "", "intro", "", "## Part", "", "body"])
    chunks = chunk_document(_doc(body, audience="manager"))
    assert [c.heading for c in chunks] == ["Doc A", "Part"]
    first = chunks[0]
    assert (first.doc_id, first.title, first.doc_type, first.audience) == (
        "doc-a",
        "Doc A",
        "policy",
        "manager",
    )
    assert first.path == Path("doc-a.md") and first.chunk_id == "doc-a#0"


def test_text_before_the_first_heading_uses_the_title_and_empty_sections_are_dropped() -> None:
    body = "\n".join(["preamble words", "", "## Empty", "", "## Full", "", "body"])
    chunks = chunk_document(_doc(body))
    assert [c.heading for c in chunks] == ["Doc A", "Full"]


def test_unclosed_fence_fails_loudly() -> None:
    with pytest.raises(DataLoadError, match="unclosed fenced block"):
        chunk_document(_doc("\n".join(["## One", "", FENCE, "never closed"])))


def test_every_synthetic_document_yields_chunks(data_dir: Path) -> None:
    documents = load_documents(data_dir / "docs")
    chunks = chunk_documents(documents)
    assert {c.doc_id for c in chunks} == {d.doc_id for d in documents}
    assert len({c.chunk_id for c in chunks}) == len(chunks)
