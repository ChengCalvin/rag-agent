"""Document loader: parse markdown files with YAML front-matter (task 2.1, 2.4; ARCH-CFG-2).

Pure file parsing; no network, no model. The chunker, embedder and index (chunk 4) build on
these `Document` values and reuse `fenced_blocks`.
"""

import re
from pathlib import Path

import yaml

from novamart_agent.errors import DataLoadError
from novamart_agent.models import AUDIENCES, DOC_TYPES, Document
from novamart_agent.parsing import as_mapping, require_str

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)
_FENCE = "`" * 3
_RESERVED_KEYS = frozenset({"id", "title", "doc_type", "audience"})


def is_fence_line(line: str) -> bool:
    """True when `line` opens or closes a fenced code block."""
    return line.strip().startswith(_FENCE)


def parse_document(path: Path) -> Document:
    """Parse one document file into a `Document`; raise `DataLoadError` if it is malformed."""
    source = path.name
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise DataLoadError(f"{source}: missing front-matter block")
    try:
        raw = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        raise DataLoadError(f"{source}: front-matter is not valid YAML") from None
    front = as_mapping(raw, f"{source} front-matter")
    doc_type = require_str(front, "doc_type", source)
    audience = require_str(front, "audience", source)
    if doc_type not in DOC_TYPES:
        raise DataLoadError(f"{source}: unknown doc_type")
    if audience not in AUDIENCES:
        raise DataLoadError(f"{source}: unknown audience")
    return Document(
        doc_id=require_str(front, "id", source),
        title=require_str(front, "title", source),
        doc_type=doc_type,
        audience=audience,
        path=path,
        body=match.group(2),
        metadata={k: v for k, v in front.items() if k not in _RESERVED_KEYS},
    )


def load_documents(docs_dir: Path) -> tuple[Document, ...]:
    """Load every `*.md` file in `docs_dir`, sorted by file name; ids must be unique."""
    documents = tuple(parse_document(p) for p in sorted(docs_dir.glob("*.md")))
    ids = [d.doc_id for d in documents]
    if len(ids) != len(set(ids)):
        raise DataLoadError(f"{docs_dir.name}: duplicate document id")
    return documents


def fenced_blocks(text: str) -> list[str]:
    """Return the inner text of each fenced code block in `text`, fences excluded.

    An unclosed fence raises, so a truncated diagram is never returned as intact.
    """
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if is_fence_line(line):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    if current is not None:
        raise DataLoadError("unclosed fenced block")
    return blocks
