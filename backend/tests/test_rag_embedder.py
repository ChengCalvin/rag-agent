"""Task 4.1: per-chunk embedding with a content-hash disk cache (TEST-1). No network, no key."""

import math
from pathlib import Path

import pytest

from fakes import FakeEmbeddingClient, build_fake_search, retrieval_settings
from novamart_agent.errors import EmbeddingError
from novamart_agent.rag import Embedder, chunk_documents, load_documents
from novamart_agent.rag.embedder import QUERY_CACHE_SIZE


def test_cached_vectors_are_reused_on_a_second_build(data_dir: Path, tmp_path: Path) -> None:
    docs, cache = data_dir / "docs", tmp_path / "cache"
    chunk_count = len(chunk_documents(load_documents(docs)))
    first = FakeEmbeddingClient()
    build_fake_search(docs, cache, first, retrieval_settings())
    assert len(first.calls) == chunk_count  # one call per chunk, none batched
    assert {task for _, task, _ in first.calls} == {"RETRIEVAL_DOCUMENT"}
    second = FakeEmbeddingClient()
    build_fake_search(docs, cache, second, retrieval_settings())
    assert second.calls == []  # second build makes zero embed calls


def test_changed_embedding_model_id_invalidates_the_cache(data_dir: Path, tmp_path: Path) -> None:
    docs, cache = data_dir / "docs", tmp_path / "cache"
    build_fake_search(docs, cache, FakeEmbeddingClient(), retrieval_settings(model="emb-1"))
    other = FakeEmbeddingClient()
    build_fake_search(docs, cache, other, retrieval_settings(model="emb-2"))
    assert other.calls and {model for model, _, _ in other.calls} == {"emb-2"}


def test_query_uses_retrieval_query_task_and_reports_cache_hit(tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder(client, "emb-1", tmp_path / "cache")
    miss = embedder.embed_query("return window")
    hit = embedder.embed_query("return window")
    assert (miss.cache_hit, hit.cache_hit) == (False, True)
    assert miss.vector == hit.vector
    assert client.calls == [("emb-1", "RETRIEVAL_QUERY", "return window")]


def test_document_and_query_vectors_are_cached_separately(tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder(client, "emb-1", tmp_path / "cache")
    embedder.embed_document("same text")
    assert embedder.embed_query("same text").cache_hit is False


def test_corrupt_cache_entry_is_re_embedded(tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    cache = tmp_path / "cache"
    embedder = Embedder(client, "emb-1", cache)
    embedder.embed_document("some text")
    (entry,) = cache.glob("*.json")
    entry.write_text("not json", encoding="utf-8")
    embedder.embed_document("some text")
    assert len(client.calls) == 2


def test_failed_embedding_call_raises_a_typed_error_and_caches_nothing(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    embedder = Embedder(FakeEmbeddingClient(fail=True), "emb-1", cache)
    with pytest.raises(EmbeddingError):
        embedder.embed_query("anything")
    assert not cache.exists() or not list(cache.glob("*.json"))


def test_repeated_identical_query_is_a_memory_hit_with_one_call(tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder(client, "emb-1", tmp_path / "cache")
    results = [embedder.embed_query("return window") for _ in range(3)]
    assert [r.cache_hit for r in results] == [False, True, True]
    assert len(client.calls) == 1


def test_query_cache_evicts_the_oldest_after_the_cap(tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    embedder = Embedder(client, "emb-1", tmp_path / "cache")
    for n in range(QUERY_CACHE_SIZE + 1):
        embedder.embed_query(f"query number {n}")
    assert embedder.embed_query(f"query number {QUERY_CACHE_SIZE}").cache_hit is True
    assert embedder.embed_query("query number 0").cache_hit is False  # evicted


def test_queries_write_no_files(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    embedder = Embedder(FakeEmbeddingClient(), "emb-1", cache)
    for n in range(5):
        embedder.embed_query(f"distinct query {n}")
    assert not cache.exists() or not list(cache.iterdir())


def test_orphan_tmp_files_are_removed_on_construction(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "abc.json.123.tmp").write_text("[1.0]", encoding="utf-8")
    (cache / "keep.json").write_text("[1.0]", encoding="utf-8")
    Embedder(FakeEmbeddingClient(), "emb-1", cache)
    assert [p.name for p in cache.iterdir()] == ["keep.json"]


@pytest.mark.parametrize("raw", ["[NaN, 1.0]", "[1.0, Infinity]", "[-Infinity]"])
def test_non_finite_cached_vector_is_a_miss_and_re_embedded(tmp_path: Path, raw: str) -> None:
    client = FakeEmbeddingClient()
    cache = tmp_path / "cache"
    embedder = Embedder(client, "emb-1", cache)
    embedder.embed_document("some text")
    (entry,) = cache.glob("*.json")
    entry.write_text(raw, encoding="utf-8")
    vector = embedder.embed_document("some text")
    assert len(client.calls) == 2 and all(math.isfinite(v) for v in vector)
