"""Task 5.2: the pure eligibility rule (Spec: "Within the return window", "Category exception",
"Policy cannot be determined"). Reference date 2026-11-23 (data/README.md).
"""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from novamart_agent.adapters import OrdersApi
from novamart_agent.errors import OrderDataError, PolicyParametersError
from novamart_agent.models import Document, Order
from novamart_agent.pipeline import evaluate_return, load_return_policy
from novamart_agent.rag import load_documents

TODAY = date(2026, 11, 23)


@pytest.fixture(scope="module")
def documents(data_dir: Path) -> tuple[Document, ...]:
    return load_documents(data_dir / "docs")


@pytest.fixture(scope="module")
def backend(data_dir: Path) -> OrdersApi:
    return OrdersApi.from_file(data_dir / "orders.json")


def _order(backend: OrdersApi, order_id: str) -> Order:
    order = backend.get(order_id)
    assert order is not None
    return order


def _with_meta(documents: tuple[Document, ...], **changes: object) -> tuple[Document, ...]:
    """The documents with the returns document's metadata changed; None removes a key."""
    out = []
    for doc in documents:
        if doc.doc_id == "returns-policy":
            meta = {k: v for k, v in {**doc.metadata, **changes}.items() if v is not None}
            doc = replace(doc, metadata=meta)
        out.append(doc)
    return tuple(out)


def test_policy_parameters_are_read_from_the_document_front_matter(
    documents: tuple[Document, ...],
) -> None:
    policy = load_return_policy(documents)
    assert policy.document_id == "returns-policy" and policy.window_days == 30
    assert "gift_cards" in policy.excluded_categories
    assert [(e.category, e.window_days) for e in policy.category_exceptions] == [
        ("electronics", 14)
    ]
    changed = load_return_policy(_with_meta(documents, return_window_days=7))
    assert changed.window_days == 7  # nothing is hard-coded


def test_within_window_electronics_5_days_is_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    verdict = evaluate_return(_order(backend, "NM-480101"), load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason, verdict.days_since_delivery) == (
        True,
        "within_window",
        5,
    )


def test_within_window_home_8_days_is_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    verdict = evaluate_return(_order(backend, "NM-480201"), load_return_policy(documents), TODAY)
    assert verdict.eligible and verdict.days_since_delivery == 8


def test_category_exception_electronics_20_days_is_not_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    verdict = evaluate_return(_order(backend, "NM-480102"), load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason, verdict.days_since_delivery) == (
        False,
        "category_exception",
        20,
    )
    assert verdict.items[0].window_days == 14


def test_outside_window_apparel_45_days_is_not_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    verdict = evaluate_return(_order(backend, "NM-480202"), load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason) == (False, "outside_window")


def test_excluded_category_gift_card_is_not_eligible_and_lines_are_reported(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    verdict = evaluate_return(_order(backend, "NM-480301"), load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason) == (False, "excluded_category")
    assert [(i.category, i.eligible) for i in verdict.items] == [
        ("gift_cards", False),
        ("home", True),
    ]


def test_window_boundary_is_inclusive_and_the_day_after_is_not(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    policy = load_return_policy(documents)
    order = _order(backend, "NM-480201")  # home, delivered 2026-11-15
    assert evaluate_return(order, policy, date(2026, 12, 15)).eligible  # day 30
    assert evaluate_return(order, policy, date(2026, 12, 16)).reason == "outside_window"  # day 31
    electronics = _order(backend, "NM-480101")  # delivered 2026-11-18
    assert evaluate_return(electronics, policy, date(2026, 12, 2)).eligible  # day 14
    assert evaluate_return(electronics, policy, date(2026, 12, 3)).reason == "category_exception"
    assert evaluate_return(electronics, policy, date(2026, 12, 19)).reason == "outside_window"


def test_non_returnable_condition_is_not_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    order = _order(backend, "NM-480201")
    used = replace(order, items=(replace(order.items[0], condition="used"),))
    verdict = evaluate_return(used, load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason) == (False, "non_returnable_condition")


def test_category_and_condition_matching_ignores_case_and_whitespace(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    order = _order(backend, "NM-480301")  # gift_cards + home
    gift = replace(order.items[0], category=" Gift_Cards ")
    verdict = evaluate_return(replace(order, items=(gift,)), load_return_policy(documents), TODAY)
    assert (verdict.eligible, verdict.reason) == (False, "excluded_category")
    policy = load_return_policy(_with_meta(documents, excluded_categories=["  GIFT_cards"]))
    assert evaluate_return(replace(order, items=(gift,)), policy, TODAY).reason == (
        "excluded_category"
    )
    used = replace(order.items[1], condition="Used ")
    verdict = evaluate_return(replace(order, items=(used,)), load_return_policy(documents), TODAY)
    assert verdict.reason == "non_returnable_condition"


def test_category_exception_lookup_ignores_case(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    order = _order(backend, "NM-480101")  # electronics, delivered 2026-11-18
    item = replace(order.items[0], category="Electronics")
    verdict = evaluate_return(replace(order, items=(item,)), load_return_policy(documents), TODAY)
    assert verdict.items[0].window_days == 14


def test_duplicate_category_exceptions_are_undeterminable(
    documents: tuple[Document, ...],
) -> None:
    dup = [
        {"category": "electronics", "window_days": 14},
        {"category": " Electronics", "window_days": 60},
    ]
    with pytest.raises(PolicyParametersError):
        load_return_policy(_with_meta(documents, category_exceptions=dup))


def test_return_window_above_the_maximum_is_undeterminable(
    documents: tuple[Document, ...],
) -> None:
    assert load_return_policy(_with_meta(documents, return_window_days=365)).window_days == 365
    with pytest.raises(PolicyParametersError):
        load_return_policy(_with_meta(documents, return_window_days=366))
    with pytest.raises(PolicyParametersError):
        load_return_policy(
            _with_meta(documents, category_exceptions=[{"category": "home", "window_days": 9999}])
        )


def test_in_transit_and_already_returned_orders_are_not_eligible(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    policy = load_return_policy(documents)
    assert evaluate_return(_order(backend, "NM-480103"), policy, TODAY).reason == "not_delivered"
    assert evaluate_return(_order(backend, "NM-480104"), policy, TODAY).reason == "already_returned"


@pytest.mark.parametrize(
    "changes",
    [
        {"return_window_days": None},
        {"return_window_days": "30"},
        {"return_window_days": True},
        {"return_window_days": 0},
        {"excluded_categories": None},
        {"excluded_categories": "gift_cards"},
        {"excluded_categories": [1]},
        {"category_exceptions": None},
        {"category_exceptions": ["electronics"]},
        {"category_exceptions": [{"category": "electronics"}]},
        {"category_exceptions": [{"window_days": 14}]},
        {"category_exceptions": [{"category": "electronics", "window_days": "14"}]},
        {"non_returnable_conditions": None},
        {"non_returnable_conditions": {"used": True}},
    ],
)
def test_missing_or_wrongly_typed_parameters_are_undeterminable(
    documents: tuple[Document, ...], changes: dict[str, object]
) -> None:
    with pytest.raises(PolicyParametersError):
        load_return_policy(_with_meta(documents, **changes))


def test_missing_returns_document_is_undeterminable(documents: tuple[Document, ...]) -> None:
    others = tuple(d for d in documents if d.doc_id != "returns-policy")
    with pytest.raises(PolicyParametersError):
        load_return_policy(others)


def test_delivered_order_with_no_or_future_delivery_date_is_undeterminable(
    backend: OrdersApi, documents: tuple[Document, ...]
) -> None:
    policy = load_return_policy(documents)
    order = _order(backend, "NM-480101")
    for bad in (None, date(2027, 1, 1)):
        with pytest.raises(OrderDataError):
            evaluate_return(replace(order, delivered_date=bad), policy, TODAY)
    with pytest.raises(OrderDataError):
        evaluate_return(replace(order, items=()), policy, TODAY)
