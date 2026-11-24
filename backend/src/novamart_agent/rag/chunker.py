"""Chunker: split a document by markdown heading, never inside a fenced code block (task 4.1).

Pure text processing, no I/O. A `#` line inside a fence is code, not a heading, so a fenced
diagram always stays whole in one chunk.
"""

import re

from novamart_agent.errors import DataLoadError
from novamart_agent.models import Chunk, Document
from novamart_agent.rag.documents import is_fence_line

_NEWLINE = chr(10)
_HEADING = re.compile(r"^#{1,6}\s+(\S.*?)\s*#*\s*$")


def _section(heading: str, heading_line: str | None, lines: list[str]) -> tuple[str, str] | None:
    """Return (heading, text) for a section, or None when it has no body worth indexing."""
    body = _NEWLINE.join(lines).strip()
    if not body:
        return None
    return heading, body if heading_line is None else f"{heading_line}{_NEWLINE}{_NEWLINE}{body}"


def _split_sections(document: Document) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading, heading_line = document.title, None
    lines: list[str] = []
    in_fence = False
    for line in document.body.splitlines():
        if is_fence_line(line):
            in_fence = not in_fence
        match = None if in_fence or is_fence_line(line) else _HEADING.match(line)
        if match is None:
            lines.append(line)
            continue
        section = _section(heading, heading_line, lines)
        if section is not None:
            sections.append(section)
        heading, heading_line, lines = match.group(1), line.strip(), []
    if in_fence:
        raise DataLoadError(f"{document.path.name}: unclosed fenced block")
    section = _section(heading, heading_line, lines)
    if section is not None:
        sections.append(section)
    return sections


def chunk_document(document: Document) -> tuple[Chunk, ...]:
    """Split `document` into one chunk per heading section, carrying its metadata.

    A section that is only a heading line (no body) is dropped. The chunk text keeps the
    heading line so the section reads on its own.
    """
    return tuple(
        Chunk(
            chunk_id=f"{document.doc_id}#{index}",
            doc_id=document.doc_id,
            title=document.title,
            heading=heading,
            path=document.path,
            doc_type=document.doc_type,
            audience=document.audience,
            text=text,
        )
        for index, (heading, text) in enumerate(_split_sections(document))
    )


def chunk_documents(documents: tuple[Document, ...]) -> tuple[Chunk, ...]:
    """Chunk every document, in order."""
    return tuple(chunk for document in documents for chunk in chunk_document(document))
