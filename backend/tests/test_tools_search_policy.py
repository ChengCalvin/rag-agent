"""Task 4.2: `search_policy` returns chunks or `no_answer`, with `embedding_cache_hit` in every
result (Spec: "Answerable policy question", "Question the documents are silent on",
"Out-of-domain question", "Employee asks about manager-only content").
"""

import inspect
import shutil
from pathlib import Path

import pytest

from fakes import (
    EMPLOYEE_STORE7,
    MANAGER_STORE7,
    UNKNOWN_ROLE_PRINCIPAL,
    FakeEmbeddingClient,
    FakeToolContext,
    build_fake_search,
    fake_tool_context,
    retrieval_settings,
)
from novamart_agent.models import Principal
from novamart_agent.rag import PolicySearch
from novamart_agent.tools import make_search_policy, parse_query, run_search_policy

DOCUMENTED_KEYS = {"text", "document_id", "section_heading", "file_path", "doc_type", "score"}
# A blocked search (blank, over-long, no principal): nothing was embedded.
NOT_EMBEDDED_NO_ANSWER = {
    "status": "no_answer",
    "embedding_cache_hit": False,
    "embedded": False,
    "closest_titles": [],
}


@pytest.fixture
def search(data_dir: Path, tmp_path: Path) -> PolicySearch:
    return build_fake_search(
        data_dir / "docs", tmp_path / "cache", FakeEmbeddingClient(), retrieval_settings()
    )


def _call(search: PolicySearch, principal: Principal | None, query: object) -> dict[str, object]:
    return run_search_policy(search, fake_tool_context(principal).state, query)


def test_answerable_query_returns_ok_with_cited_chunk_fields(search: PolicySearch) -> None:
    result = _call(search, EMPLOYEE_STORE7, "electronics return window days")
    assert result["status"] == "ok" and result["embedding_cache_hit"] is False
    chunks = result["chunks"]
    assert isinstance(chunks, list) and chunks
    assert set(chunks[0]) == DOCUMENTED_KEYS
    assert chunks[0]["document_id"] == "returns-policy"
    assert chunks[0]["file_path"] == "returns-policy.md" and chunks[0]["doc_type"] == "policy"


def test_gap_query_is_no_answer_with_cache_hit_field_and_closest_titles(
    search: PolicySearch,
) -> None:
    result = _call(search, EMPLOYEE_STORE7, "bulk corporate ordering")
    assert result["status"] == "no_answer"
    assert result["embedding_cache_hit"] is False
    assert "chunks" not in result and isinstance(result["closest_titles"], list)


def test_unrelated_query_is_no_answer(search: PolicySearch) -> None:
    result = _call(search, EMPLOYEE_STORE7, "recipe pasta sauce tomatoes")
    assert result["status"] == "no_answer" and "embedding_cache_hit" in result


def test_embedding_cache_hit_is_correct_on_miss_hit_and_no_answer(search: PolicySearch) -> None:
    miss = _call(search, EMPLOYEE_STORE7, "electronics return window days")
    hit = _call(search, EMPLOYEE_STORE7, "electronics return window days")
    gap_miss = _call(search, EMPLOYEE_STORE7, "bulk corporate ordering")
    gap_hit = _call(search, EMPLOYEE_STORE7, "bulk corporate ordering")
    assert [r["embedding_cache_hit"] for r in (miss, hit, gap_miss, gap_hit)] == [
        False,
        True,
        False,
        True,
    ]
    assert (gap_miss["status"], gap_hit["status"]) == ("no_answer", "no_answer")


def test_employee_asking_about_manager_only_content_gets_no_answer(search: PolicySearch) -> None:
    query = "NovaBook launch rollout waves"
    result = _call(search, EMPLOYEE_STORE7, query)
    assert result["status"] == "no_answer"
    assert "NovaBook" not in repr(result) and "Managers Only" not in repr(result)


def test_manager_asking_the_same_question_gets_the_manager_document(search: PolicySearch) -> None:
    result = _call(search, MANAGER_STORE7, "NovaBook launch rollout waves")
    chunks = result["chunks"]
    assert result["status"] == "ok" and isinstance(chunks, list)
    assert chunks[0]["document_id"] == "product-novabook-launch-briefing"


def test_no_principal_and_unknown_role_get_no_answer(search: PolicySearch) -> None:
    for principal in (None, UNKNOWN_ROLE_PRINCIPAL):
        result = _call(search, principal, "electronics return window days")
        assert result == NOT_EMBEDDED_NO_ANSWER


@pytest.mark.parametrize("raw", [None, "", "   \n\t", 42, ["a"], {"q": "a"}])
def test_blank_or_malformed_query_is_no_answer_and_never_raises(
    search: PolicySearch, raw: object
) -> None:
    assert parse_query(raw) is None
    result = _call(search, EMPLOYEE_STORE7, raw)
    assert result == NOT_EMBEDDED_NO_ANSWER


def test_embedding_outage_returns_generic_error_status_not_an_exception(
    data_dir: Path, tmp_path: Path
) -> None:
    client = FakeEmbeddingClient()
    built = build_fake_search(data_dir / "docs", tmp_path / "cache", client, retrieval_settings())
    client.fail = True  # the index was built while it worked; the query-time call now fails
    result = run_search_policy(built, fake_tool_context(EMPLOYEE_STORE7).state, "uncached query")
    assert result == {"status": "error", "embedding_cache_hit": False, "embedded": False}


def test_tool_has_no_identity_parameter_and_reads_the_principal_from_state(
    search: PolicySearch,
) -> None:
    tool = make_search_policy(search)
    assert tool.__name__ == "search_policy"
    assert list(inspect.signature(tool).parameters) == ["query", "tool_context"]
    context = FakeToolContext(state=fake_tool_context(EMPLOYEE_STORE7).state)
    assert tool("electronics return window days", context)["status"] == "ok"
    assert tool("NovaBook launch rollout waves", context)["status"] == "no_answer"


def test_over_long_query_is_no_answer_with_zero_embed_calls(data_dir: Path, tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    built = build_fake_search(data_dir / "docs", tmp_path / "cache", client, retrieval_settings())
    before = len(client.calls)
    result = run_search_policy(built, fake_tool_context(EMPLOYEE_STORE7).state, "return " * 100)
    assert result == NOT_EMBEDDED_NO_ANSWER
    assert len(client.calls) == before


def test_embedded_is_true_only_for_a_real_embedding_call(data_dir: Path, tmp_path: Path) -> None:
    client = FakeEmbeddingClient()
    built = build_fake_search(data_dir / "docs", tmp_path / "cache", client, retrieval_settings())
    state = fake_tool_context(EMPLOYEE_STORE7).state
    seen: list[tuple[object, int]] = []
    for query in ("electronics return window days", "electronics return window days"):
        before = len(client.calls)
        result = run_search_policy(built, state, query)  # ok: a miss, then a cache hit
        seen.append((result["embedded"], len(client.calls) - before))
    before = len(client.calls)
    gap = run_search_policy(built, state, "bulk corporate ordering")  # no_answer after a search
    seen.append((gap["embedded"], len(client.calls) - before))
    assert seen == [(True, 1), (False, 0), (True, 1)]


def test_a_search_over_an_empty_permitted_corpus_is_embedded_with_no_chunks(
    data_dir: Path, tmp_path: Path
) -> None:
    only_manager = tmp_path / "mgr"
    only_manager.mkdir()
    shutil.copy(data_dir / "docs" / "manager-approvals.md", only_manager)
    client = FakeEmbeddingClient()
    built = build_fake_search(only_manager, tmp_path / "cache", client, retrieval_settings())
    client.calls.clear()
    result = run_search_policy(built, fake_tool_context(EMPLOYEE_STORE7).state, "return window")
    assert len(client.calls) == 1
    assert result["status"] == "no_answer" and result["embedded"] is True
    assert result["closest_titles"] == []


def test_query_exactly_at_the_cap_is_searched(search: PolicySearch) -> None:
    cap = search.max_query_chars
    query = "electronics return window days " + "x" * (cap - 31)
    assert len(query) == cap and parse_query(query, cap) == query
    assert parse_query(query + "x", cap) is None
    assert _call(search, EMPLOYEE_STORE7, query)["status"] in {"ok", "no_answer"}


def test_control_characters_are_stripped_and_whitespace_becomes_a_space() -> None:
    assert parse_query("ret\x00urn\x07 win\x1bdow\tdays\nnow") == "return window days now"
    assert parse_query("\x00\x01\x02") is None
