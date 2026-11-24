"""Chunker, embedder (the only google-genai importer), index and search.

Public names are exposed here (ARCH-MOD-2); other packages import only these.
"""

from novamart_agent.rag.catalog import build_catalog
from novamart_agent.rag.chunker import chunk_document, chunk_documents
from novamart_agent.rag.contact import escalation_contact
from novamart_agent.rag.documents import fenced_blocks, load_documents, parse_document
from novamart_agent.rag.embedder import (
    Embedder,
    EmbeddingClient,
    GenaiEmbeddingClient,
    QueryEmbedding,
)
from novamart_agent.rag.index import CosineIndex, ScoredChunk, closest_titles
from novamart_agent.rag.lazy import LazyPolicySearch
from novamart_agent.rag.search import (
    MAX_CLOSEST_TITLES,
    PolicySearch,
    SearchResult,
    SearchService,
    build_policy_search,
)

__all__: list[str] = [
    "MAX_CLOSEST_TITLES",
    "CosineIndex",
    "Embedder",
    "EmbeddingClient",
    "GenaiEmbeddingClient",
    "LazyPolicySearch",
    "PolicySearch",
    "QueryEmbedding",
    "ScoredChunk",
    "SearchResult",
    "SearchService",
    "build_catalog",
    "build_policy_search",
    "chunk_document",
    "chunk_documents",
    "closest_titles",
    "escalation_contact",
    "fenced_blocks",
    "load_documents",
    "parse_document",
]
