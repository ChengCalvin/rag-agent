"""Policy search service: embed the query, rank permitted chunks, gate on the threshold
(task 4.2, D4, D13 case C). Pure apart from the injected embedder; no ADK imports.
"""

from dataclasses import dataclass
from typing import Protocol

from novamart_agent.config import Settings
from novamart_agent.models import Document
from novamart_agent.rag.chunker import chunk_documents
from novamart_agent.rag.embedder import Embedder
from novamart_agent.rag.index import CosineIndex, ScoredChunk, closest_titles

MAX_CLOSEST_TITLES = 3


@dataclass(frozen=True)
class SearchResult:
    """What a search found for one caller.

    `hits` is empty when nothing reached the threshold (or the caller may see nothing);
    `closest_titles` then still names up to three permitted documents. `embedding_cache_hit`
    is False when no embedding was needed or the query was embedded by a billed call.
    `embedded` is True only when a query embedding was obtained from the embedding API (a cache
    miss that made the call): False for a blocked search and for a cache hit.
    """

    hits: tuple[ScoredChunk, ...]
    closest_titles: tuple[str, ...]
    embedding_cache_hit: bool
    embedded: bool


class SearchService(Protocol):
    """What the `search_policy` tool needs: a ready search, or a lazy stand-in for one."""

    @property
    def max_query_chars(self) -> int: ...

    def search(self, query: str, audiences: frozenset[str]) -> SearchResult: ...


class PolicySearch:
    """Searches the embedded chunks for a caller with a given set of permitted audiences."""

    def __init__(self, index: CosineIndex, embedder: Embedder, settings: Settings) -> None:
        self._index = index
        self._embedder = embedder
        self._threshold = settings.similarity_threshold
        self._top_k = settings.top_k
        self.max_query_chars = settings.max_query_chars

    def search(self, query: str, audiences: frozenset[str]) -> SearchResult:
        """Rank the chunks `audiences` may see; keep the top-k at or above the threshold."""
        if not audiences:
            return SearchResult((), (), False, False)  # deny by default: no embedding, no network
        embedded = self._embedder.embed_query(query)
        ranked = self._index.rank(embedded.vector, audiences)
        hits = tuple(s for s in ranked[: self._top_k] if s.score >= self._threshold)
        titles = closest_titles(ranked, MAX_CLOSEST_TITLES)
        return SearchResult(hits, titles, embedded.cache_hit, not embedded.cache_hit)


def build_policy_search(
    documents: tuple[Document, ...], embedder: Embedder, settings: Settings
) -> PolicySearch:
    """Chunk and embed every document (one call per chunk, cached) and build the search."""
    chunks = chunk_documents(documents)
    vectors = [embedder.embed_document(f"{c.title}: {c.text}") for c in chunks]
    return PolicySearch(CosineIndex(chunks, vectors), embedder, settings)
