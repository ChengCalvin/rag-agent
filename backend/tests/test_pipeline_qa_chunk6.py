"""QA gap tests for chunk 6 (tasks 6.2-6.5), written against the spec scenarios, not the code.

Three tests first pinned real defects (QA6-1, QA6-2, QA6-3, see docs/qa-report.md) as strict
xfails; the defects are fixed and the markers are removed.
"""

import shutil
from pathlib import Path

import pytest

from fakes import (
    EMPLOYEE_STORE7,
    EMPLOYEE_STORE12,
    FakeEmbeddingClient,
    build_fake_search,
    build_order_guard,
    fake_tool_context,
    retrieval_settings,
)
from novamart_agent.config import DEFAULT_PRICES
from novamart_agent.pipeline import (
    SessionCost,
    UsageRecord,
    add_turn,
    compute_turn_cost,
    embedding_billed,
    render_cost_line,
    sanitize_model_text,
)
from novamart_agent.prompts import NOT_FOUND_REPLY
from novamart_agent.rag import PolicySearch
from novamart_agent.tools import run_get_order_status, run_search_policy

FENCE = "`" * 3
TILDE = "~" * 3
DIAGRAM = "+-----+\n| Hub |\n+-----+"
CHUNK_TEXT = f"## Setup\n\n{FENCE}\n{DIAGRAM}\n{FENCE}\n"


def test_an_unclosed_fence_is_stripped_even_when_its_content_equals_a_verified_diagram() -> None:
    # The closing fence is missing but the body is exactly a chunk diagram: still stripped.
    reply = f"Intro.\n{FENCE}\n{DIAGRAM}"
    assert sanitize_model_text(reply, [CHUNK_TEXT]) == "Intro."


def test_a_diagram_that_is_only_part_of_a_chunk_diagram_is_stripped() -> None:
    reply = f"{FENCE}\n+-----+\n| Hub |\n{FENCE}"
    assert sanitize_model_text(reply, [CHUNK_TEXT]) == ""


def test_a_model_invented_diagram_in_a_tilde_fence_is_stripped() -> None:
    reply = f"Layout:\n{TILDE}mermaid\ngraph TD\n  X-->Y\n{TILDE}\nDone."
    assert "X-->Y" not in sanitize_model_text(reply, [CHUNK_TEXT])


def test_a_model_written_confidence_line_without_a_colon_is_removed() -> None:
    cleaned = sanitize_model_text("Answer.\nConfidence - High\nTail", [])
    assert "High" not in cleaned


def test_denial_causes_give_one_identical_tool_result_and_one_identical_cost_line(
    data_dir: Path,
) -> None:
    # Nonexistent, out-of-scope (other store) and malformed ids, through the real guard and
    # adapter. Parity needs the tool result to be the same dict, so the code reply and the cost
    # line built from the same recorded calls cannot differ by cause.
    guard = build_order_guard(data_dir)
    state = fake_tool_context(EMPLOYEE_STORE7).state
    other_store_order = "NM-480101"
    # NM-480101 belongs to store-7 in the seed; use a store-12 employee to make it out of scope.
    out_of_scope = run_get_order_status(
        build_order_guard(data_dir), fake_tool_context(EMPLOYEE_STORE12).state, other_store_order
    )
    results = [
        run_get_order_status(guard, state, "NM-999999"),  # nonexistent
        out_of_scope,
        run_get_order_status(guard, state, "10x2"),  # malformed
    ]
    assert results[0] == results[1] == results[2] == {"status": "not_found"}
    records = [UsageRecord("chat", "intake", "gemini-3.6-flash", 500, 40)]
    lines = [
        render_cost_line(
            compute_turn_cost(records, DEFAULT_PRICES),
            add_turn(SessionCost(), compute_turn_cost(records, DEFAULT_PRICES)),
        )
        for _ in results
    ]
    assert len(set(lines)) == 1
    assert "?" not in NOT_FOUND_REPLY


def _search(
    data_dir: Path, tmp_path: Path, docs: Path | None = None
) -> tuple[PolicySearch, FakeEmbeddingClient]:
    client = FakeEmbeddingClient()
    search = build_fake_search(
        docs or data_dir / "docs", tmp_path / "cache", client, retrieval_settings(threshold=0.2)
    )
    client.calls.clear()
    return search, client


@pytest.mark.parametrize(
    ("query", "principal_ok"),
    [
        ("   ", True),  # blank
        ("x" * 600, True),  # over-long
        ("return window electronics refund", False),  # no principal
        ("return window electronics refund", True),  # ok miss, then repeated as a hit
        ("zzzz qqqq wwww", True),  # no_answer after a real search
    ],
)
def test_embedding_is_billed_exactly_when_a_real_embedding_call_was_made(
    data_dir: Path, tmp_path: Path, query: str, principal_ok: bool
) -> None:
    search, client = _search(data_dir, tmp_path)
    state = fake_tool_context(EMPLOYEE_STORE7 if principal_ok else None).state
    for _ in range(2):  # the second round is a cache hit when the first embedded the query
        before = len(client.calls)
        result = run_search_policy(search, state, query)
        assert embedding_billed(result) == (len(client.calls) > before)


def test_a_search_over_an_empty_permitted_corpus_is_billed_for_its_real_embedding_call(
    data_dir: Path, tmp_path: Path
) -> None:
    only_manager = tmp_path / "mgr"
    only_manager.mkdir()
    shutil.copy(data_dir / "docs" / "manager-approvals.md", only_manager)
    search, client = _search(data_dir, tmp_path, only_manager)
    state = fake_tool_context(EMPLOYEE_STORE7).state
    result = run_search_policy(search, state, "return window electronics")
    assert len(client.calls) == 1  # a real embedding call was made
    assert embedding_billed(result)
