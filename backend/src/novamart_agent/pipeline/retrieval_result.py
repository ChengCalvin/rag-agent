"""Parse a `search_policy` result dict into typed values (ARCH-BOUND-1, TYPE-2).

The dict is produced by our own tool code, not by the model, so a wrong shape is a bug and
raises `ToolResultError` (a field name, never a value). The chunk text inside is retrieved
document text: data only (AGENT-4).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from novamart_agent.errors import ToolResultError
from novamart_agent.models import TOOL_STATUS_OK, RetrievedChunk


@dataclass(frozen=True)
class RetrievalResult:
    """A typed `search_policy` result."""

    status: str
    embedding_cache_hit: bool
    embedded: bool
    chunks: tuple[RetrievedChunk, ...]
    closest_titles: tuple[str, ...]


def _str(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise ToolResultError(f"chunk field '{key}' must be a string")
    return value


def _chunk(entry: object) -> RetrievedChunk:
    if not isinstance(entry, dict):
        raise ToolResultError("chunk must be an object")
    score = entry.get("score")
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise ToolResultError("chunk field 'score' must be a number")
    return RetrievedChunk(
        document_id=_str(entry, "document_id"),
        heading=_str(entry, "section_heading"),
        file_name=_str(entry, "file_path"),
        doc_type=_str(entry, "doc_type"),
        text=_str(entry, "text"),
        score=float(score),
    )


def _titles(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(t, str) for t in raw):
        raise ToolResultError("field 'closest_titles' must be a list of strings")
    return tuple(raw)


def parse_retrieval_result(result: Mapping[str, object]) -> RetrievalResult:
    """Type a tool result. `chunks` are read only when the status is `ok`."""
    status = result.get("status")
    if not isinstance(status, str):
        raise ToolResultError("field 'status' must be a string")
    raw_chunks = result.get("chunks")
    if status == TOOL_STATUS_OK:
        if not isinstance(raw_chunks, list):
            raise ToolResultError("field 'chunks' must be a list")
        chunks = tuple(_chunk(c) for c in raw_chunks)
    else:
        chunks = ()
    return RetrievalResult(
        status,
        result.get("embedding_cache_hit") is True,
        result.get("embedded") is True,
        chunks,
        _titles(result.get("closest_titles")),
    )
