"""Tasks 4.1 and 4.2: audience filter, threshold gate, closest titles, escalation contact
(Spec: "Retrieval respects document audience", "Low-confidence retrieval produces a refusal").
"""

from dataclasses import replace
from pathlib import Path

import pytest

from fakes import (
    EMPLOYEE_STORE7,
    MANAGER_STORE7,
    REGIONAL_NORTH,
    UNKNOWN_ROLE_PRINCIPAL,
    FakeEmbeddingClient,
    build_fake_search,
    retrieval_settings,
)
from novamart_agent.errors import EscalationContactError
from novamart_agent.models import Document
from novamart_agent.rag import PolicySearch, escalation_contact, load_documents
from novamart_agent.security import permitted_audiences

MANAGER_ONLY_DOCS = {"manager-approvals", "product-novabook-launch-briefing"}


@pytest.fixture
def search(data_dir: Path, tmp_path: Path) -> PolicySearch:
    return build_fake_search(
        data_dir / "docs", tmp_path / "cache", FakeEmbeddingClient(), retrieval_settings()
    )


def test_manager_only_chunk_is_never_returned_to_a_non_manager(search: PolicySearch) -> None:
    queries = ["discount override approval regional manager", "NovaBook launch rollout waves"]
    for query in queries:
        result = search.search(query, permitted_audiences(EMPLOYEE_STORE7))
        assert all(h.chunk.doc_id not in MANAGER_ONLY_DOCS for h in result.hits)
        assert all(t not in result.closest_titles for t in _restricted_titles())


def test_manager_asks_the_same_question_and_gets_the_manager_document(
    search: PolicySearch,
) -> None:
    for role in (MANAGER_STORE7, REGIONAL_NORTH):
        result = search.search(
            "discount override approval regional manager", permitted_audiences(role)
        )
        assert result.hits and result.hits[0].chunk.doc_id == "manager-approvals"


def test_answerable_query_returns_chunks_with_scores_above_threshold(search: PolicySearch) -> None:
    result = search.search("electronics return window days", permitted_audiences(EMPLOYEE_STORE7))
    assert result.hits[0].chunk.doc_id == "returns-policy"
    assert all(h.score >= 0.2 for h in result.hits) and len(result.hits) <= 3


def test_gap_and_unrelated_queries_have_no_hits(search: PolicySearch) -> None:
    for query in ("bulk corporate ordering", "recipe pasta sauce tomatoes"):
        assert search.search(query, permitted_audiences(EMPLOYEE_STORE7)).hits == ()


def test_closest_titles_never_leak_a_restricted_title_to_a_non_manager(
    search: PolicySearch,
) -> None:
    result = search.search(
        "NovaBook launch rollout waves stores", permitted_audiences(EMPLOYEE_STORE7)
    )
    assert result.closest_titles and len(result.closest_titles) <= 3
    assert set(result.closest_titles).isdisjoint(_restricted_titles())


def test_closest_titles_are_independent_of_the_threshold(data_dir: Path, tmp_path: Path) -> None:
    strict = retrieval_settings(threshold=1.0)
    search = build_fake_search(data_dir / "docs", tmp_path / "cache", FakeEmbeddingClient(), strict)
    result = search.search("electronics return window days", permitted_audiences(EMPLOYEE_STORE7))
    assert result.hits == ()
    assert result.closest_titles[0] == "Returns and Refunds Policy"


def test_manager_closest_titles_may_include_a_restricted_title(search: PolicySearch) -> None:
    result = search.search(
        "NovaBook launch rollout waves stores", permitted_audiences(MANAGER_STORE7)
    )
    assert "NovaBook Pro Launch Briefing (Managers Only)" in result.closest_titles


def test_unknown_role_and_no_principal_get_nothing_and_no_embedding_call(
    data_dir: Path, tmp_path: Path
) -> None:
    client = FakeEmbeddingClient()
    search = build_fake_search(data_dir / "docs", tmp_path / "cache", client, retrieval_settings())
    built = len(client.calls)
    for principal in (UNKNOWN_ROLE_PRINCIPAL, None):
        result = search.search("returns window", permitted_audiences(principal))
        assert (result.hits, result.closest_titles) == ((), ())
        assert (result.embedding_cache_hit, result.embedded) == (False, False)
    assert len(client.calls) == built


def test_embedding_cache_hit_is_false_on_a_miss_and_true_on_a_repeat(search: PolicySearch) -> None:
    audiences = permitted_audiences(EMPLOYEE_STORE7)
    miss = search.search("electronics return window", audiences)
    hit = search.search("electronics return window", audiences)
    assert (miss.embedding_cache_hit, miss.embedded) == (False, True)
    assert (hit.embedding_cache_hit, hit.embedded) == (True, False)


def test_escalation_contact_is_read_from_the_document_not_hard_coded(data_dir: Path) -> None:
    documents = load_documents(data_dir / "docs")
    operations = next(d for d in documents if d.doc_id == "store-operations")
    assert escalation_contact(documents) == operations.metadata["escalation_contact"]
    changed = _with_metadata(documents, {"escalation_contact": "Ring the test line 000"})
    assert escalation_contact(changed) == "Ring the test line 000"


@pytest.mark.parametrize("metadata", [{}, {"escalation_contact": "  "}, {"escalation_contact": 5}])
def test_missing_or_blank_escalation_contact_fails_loudly(
    data_dir: Path, metadata: dict[str, object]
) -> None:
    changed = _with_metadata(load_documents(data_dir / "docs"), metadata)
    with pytest.raises(EscalationContactError):
        escalation_contact(changed)


def test_missing_store_operations_document_fails_loudly(data_dir: Path) -> None:
    documents = tuple(
        d for d in load_documents(data_dir / "docs") if d.doc_id != "store-operations"
    )
    with pytest.raises(EscalationContactError):
        escalation_contact(documents)


def _restricted_titles() -> set[str]:
    return {
        "Manager Approvals and Discount Overrides",
        "NovaBook Pro Launch Briefing (Managers Only)",
    }


def _with_metadata(
    documents: tuple[Document, ...], metadata: dict[str, object]
) -> tuple[Document, ...]:
    return tuple(
        replace(d, metadata=metadata) if d.doc_id == "store-operations" else d for d in documents
    )
