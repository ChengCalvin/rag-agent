"""Cosine index in numpy with the audience filter applied before ranking (task 4.1, D4).

Pure: no network, no disk, no model. A chunk the caller may not see is removed before any
score is computed, so it can neither be returned nor influence what is.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from novamart_agent.errors import EmbeddingError
from novamart_agent.models import Chunk

Vector = list[float]


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk and its cosine similarity to the query."""

    chunk: Chunk
    score: float


def _unit_rows(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


class CosineIndex:
    """Chunk vectors held as unit rows, so cosine similarity is one matrix product."""

    def __init__(self, chunks: tuple[Chunk, ...], vectors: list[Vector]) -> None:
        if len(chunks) != len(vectors):
            raise EmbeddingError("chunk and vector counts differ")
        self._chunks = chunks
        self._matrix = _unit_rows(np.array(vectors, dtype=np.float64).reshape(len(chunks), -1))

    def rank(self, query: Vector, audiences: frozenset[str]) -> list[ScoredChunk]:
        """Chunks whose audience is in `audiences`, best score first. An empty set ranks nothing."""
        positions = [i for i, c in enumerate(self._chunks) if c.audience in audiences]
        if not positions:
            return []
        query_row = _unit_rows(np.array([query], dtype=np.float64))
        if query_row.shape[1] != self._matrix.shape[1]:
            raise EmbeddingError("query and chunk vectors differ in size")
        scores = self._matrix[positions] @ query_row[0]
        order = np.argsort(-scores, kind="stable")
        return [ScoredChunk(self._chunks[positions[i]], float(scores[i])) for i in order]


def closest_titles(ranked: list[ScoredChunk], limit: int) -> tuple[str, ...]:
    """Up to `limit` distinct document titles from an already audience-filtered ranking.

    Independent of the answer threshold: it names the nearest documents even when nothing
    scored high enough to answer.
    """
    titles: list[str] = []
    for scored in ranked:
        if scored.chunk.title not in titles:
            titles.append(scored.chunk.title)
        if len(titles) == limit:
            break
    return tuple(titles)
