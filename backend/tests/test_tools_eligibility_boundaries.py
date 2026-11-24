"""Task 5.2 QA gap closers: the exception window comes from the policy (not a constant), and the
reason code flips from category_exception to outside_window exactly after the general window.
"""

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from fakes import REGIONAL_NORTH, build_order_guard, fake_tool_context
from novamart_agent.models import Document
from novamart_agent.rag import load_documents
from novamart_agent.tools import EligibilityDeps, run_check_return_eligibility

ORDER_ELECTRONICS = "NM-480101"  # electronics, delivered 2026-11-18
DELIVERED = date(2026, 11, 18)


@pytest.fixture(scope="module")
def documents(data_dir: Path) -> tuple[Document, ...]:
    return load_documents(data_dir / "docs")


def _run(data_dir: Path, documents: tuple[Document, ...], today: date) -> dict[str, object]:
    guard = build_order_guard(data_dir)
    state = fake_tool_context(REGIONAL_NORTH).state
    deps = EligibilityDeps(guard, documents, lambda: today)
    return run_check_return_eligibility(deps, state, ORDER_ELECTRONICS)


def _with_exception_window(documents: tuple[Document, ...], window: int) -> tuple[Document, ...]:
    out = []
    for doc in documents:
        if doc.doc_id == "returns-policy":
            exceptions = [{"category": "electronics", "window_days": window}]
            doc = replace(doc, metadata={**doc.metadata, "category_exceptions": exceptions})
        out.append(doc)
    return tuple(out)


@pytest.mark.parametrize(
    ("window_and_days", "eligible"),
    [((3, 3), True), ((3, 4), False), ((25, 25), True), ((25, 26), False), ((1, 2), False)],
)
def test_exception_window_is_read_from_the_policy_not_hard_coded(
    data_dir: Path,
    documents: tuple[Document, ...],
    window_and_days: tuple[int, int],
    eligible: bool,
) -> None:
    window, days = window_and_days
    result = _run(data_dir, _with_exception_window(documents, window), DELIVERED + timedelta(days))
    assert result["eligible"] is eligible
    assert result["parameters_used"]["category_exceptions"] == [  # type: ignore[index]
        {"category": "electronics", "window_days": window}
    ]


@pytest.mark.parametrize(
    ("days", "reason"),
    [
        (14, "within_window"),
        (15, "category_exception"),
        (30, "category_exception"),
        (31, "outside_window"),
    ],
)
def test_electronics_reason_code_at_each_window_edge(
    data_dir: Path, documents: tuple[Document, ...], days: int, reason: str
) -> None:
    result = _run(data_dir, documents, DELIVERED + timedelta(days))
    assert result["reason"] == reason
    assert result["eligible"] is (reason == "within_window")
