"""Embedder: the only module that imports google-genai or touches the network or the vector
cache on disk (ARCH-EDGE-1, design D4).

One embedding call per text (several strings in one call return one aggregated vector).
Chunks use `RETRIEVAL_DOCUMENT`, queries use `RETRIEVAL_QUERY`. Vectors are cached on disk
keyed by a hash of the embedding model id, the task type and the text, so a changed model id
or changed text never reuses a stale vector. No ADK imports. Texts and vectors are never logged.
"""

import hashlib
import json
import math
import os
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from google import genai
from google.genai import types

from novamart_agent.errors import EmbeddingError

TASK_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_QUERY = "RETRIEVAL_QUERY"
_CACHE_SUFFIX = ".json"
QUERY_CACHE_SIZE = 256  # query vectors kept in memory (LRU); chunk vectors use the disk cache

Vector = list[float]


class EmbeddingClient(Protocol):
    """One embedding call. Tests pass a fake; production uses `GenaiEmbeddingClient`."""

    def embed(self, model: str, task_type: str, text: str) -> Vector: ...


@dataclass(frozen=True)
class QueryEmbedding:
    """A query vector and whether it came from the in-memory cache (no billed call)."""

    vector: Vector
    cache_hit: bool


class GenaiEmbeddingClient:
    """The google-genai client, created on first use so importing this module needs no key.

    The SDK finds the AI Studio key (`GOOGLE_API_KEY`) itself; `config` stays the only module
    in this project that reads the environment.
    """

    def __init__(self) -> None:
        self._client: genai.Client | None = None

    def embed(self, model: str, task_type: str, text: str) -> Vector:
        try:
            if self._client is None:
                self._client = genai.Client()
            response = self._client.models.embed_content(
                model=model,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            embeddings = response.embeddings
            values = embeddings[0].values if embeddings else None
        except Exception as exc:
            # Only the exception class is kept: SDK messages can echo the request.
            raise EmbeddingError(f"embedding call failed ({type(exc).__name__})") from None
        if not values:
            raise EmbeddingError("embedding reply had no vector")
        return [float(v) for v in values]


def _as_vector(raw: object) -> Vector | None:
    if not isinstance(raw, list) or not raw:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
        return None
    vector = [float(v) for v in raw]
    return vector if all(math.isfinite(v) for v in vector) else None


class Embedder:
    """Embeds texts through a client. Chunk vectors are cached on disk by content hash; query
    vectors only in a small in-memory LRU, so queries never grow the disk cache."""

    def __init__(self, client: EmbeddingClient, model: str, cache_dir: Path) -> None:
        self._client = client
        self._model = model
        self._cache_dir = cache_dir
        self._queries: OrderedDict[str, Vector] = OrderedDict()
        if cache_dir.is_dir():
            for orphan in cache_dir.glob("*.tmp"):  # left by a crash between write and replace
                orphan.unlink(missing_ok=True)

    def embed_document(self, text: str) -> Vector:
        """Embed one chunk text with `RETRIEVAL_DOCUMENT`."""
        return self._embed(TASK_DOCUMENT, text)[0]

    def embed_query(self, text: str) -> QueryEmbedding:
        """Embed a search query with `RETRIEVAL_QUERY`; `cache_hit` is True when the in-memory
        cache served it (no billed call)."""
        cached = self._queries.get(text)
        if cached is not None:
            self._queries.move_to_end(text)
            return QueryEmbedding(cached, True)
        vector = self._client.embed(self._model, TASK_QUERY, text)
        self._queries[text] = vector
        if len(self._queries) > QUERY_CACHE_SIZE:
            self._queries.popitem(last=False)
        return QueryEmbedding(vector, False)

    def _cache_path(self, task_type: str, text: str) -> Path:
        payload = json.dumps([self._model, task_type, text], ensure_ascii=False)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}{_CACHE_SUFFIX}"

    def _read(self, path: Path) -> Vector | None:
        try:
            return _as_vector(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None  # absent or corrupt entry: treated as a miss and re-embedded

    def _write(self, path: Path, vector: Vector) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(vector), encoding="utf-8")
        os.replace(temporary, path)  # atomic: a crash never leaves a half-written entry

    def _embed(self, task_type: str, text: str) -> tuple[Vector, bool]:
        path = self._cache_path(task_type, text)
        cached = self._read(path)
        if cached is not None:
            return cached, True
        vector = self._client.embed(self._model, task_type, text)
        self._write(path, vector)
        return vector, False
