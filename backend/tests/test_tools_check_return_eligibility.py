"""Task 5.2: `check_return_eligibility` at the real tool boundary (Spec: "Within the return
window", "Category exception", "Policy cannot be determined", "Malformed identifier",
"Unknown order", "Customer data is minimised").
"""

import inspect
import json
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from google.adk.tools import FunctionTool

from fakes import (
    EMPLOYEE_STORE7,
    EMPLOYEE_STORE12,
    REGIONAL_NORTH,
    UNKNOWN_ROLE_PRINCIPAL,
    FakeToolContext,
    build_order_guard,
    fake_tool_context,
)
from novamart_agent.models import Document, Principal
from novamart_agent.rag import load_documents
from novamart_agent.security import AuditLogger, OrderGuard
from novamart_agent.tools import (
    EligibilityDeps,
    make_check_return_eligibility,
    run_check_return_eligibility,
)

TODAY = date(2026, 11, 23)
NOT_FOUND = {"status": "not_found"}
MANAGER_STORE19 = Principal("mgr_store19", "Test Manager", "manager", "store-19", "south")


@pytest.fixture(scope="module")
def documents(data_dir: Path) -> tuple[Document, ...]:
    return load_documents(data_dir / "docs")


def _call(
    data_dir: Path,
    documents: tuple[Document, ...],
    principal: Principal | None,
    order_id: object,
) -> dict[str, object]:
    guard = build_order_guard(data_dir)
    state = fake_tool_context(principal).state
    return run_check_return_eligibility(
        EligibilityDeps(guard, documents, lambda: TODAY), state, order_id
    )


def _broken(documents: tuple[Document, ...]) -> tuple[Document, ...]:
    out = []
    for doc in documents:
        if doc.doc_id == "returns-policy":
            doc = replace(doc, metadata={"return_window_days": "thirty"})
        out.append(doc)
    return tuple(out)


def test_within_window_is_eligible_and_cites_the_returns_policy(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    result = _call(data_dir, documents, EMPLOYEE_STORE7, "NM-480101")
    assert result["status"] == "ok" and result["eligible"] is True
    assert result["reason"] == "within_window" and result["policy_document_id"] == "returns-policy"
    assert result["days_since_delivery"] == 5 and result["reference_date"] == "2026-11-23"
    assert result["parameters_used"] == {
        "return_window_days": 30,
        "excluded_categories": ["gift_cards", "perishable_food", "custom_orders"],
        "category_exceptions": [{"category": "electronics", "window_days": 14}],
        "non_returnable_conditions": ["used", "customer_damaged"],
    }


def test_category_exception_is_not_eligible_with_the_exception_window(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    result = _call(data_dir, documents, EMPLOYEE_STORE7, "NM-480102")
    assert (result["status"], result["eligible"], result["reason"]) == (
        "ok",
        False,
        "category_exception",
    )
    items = result["items"]
    assert isinstance(items, list) and items[0]["window_days"] == 14


def test_outside_window_is_not_eligible(data_dir: Path, documents: tuple[Document, ...]) -> None:
    result = _call(data_dir, documents, EMPLOYEE_STORE12, "NM-480202")
    assert (result["eligible"], result["reason"]) == (False, "outside_window")


def test_excluded_gift_card_is_not_eligible(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    # NM-480301 is in store-19 (south); no seeded persona is in scope, so use a store-19 manager.
    result = _call(data_dir, documents, MANAGER_STORE19, "NM-480301")
    assert (result["status"], result["eligible"], result["reason"]) == (
        "ok",
        False,
        "excluded_category",
    )


def test_undeterminable_policy_returns_not_determinable_for_a_permitted_order(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    result = _call(data_dir, _broken(documents), EMPLOYEE_STORE7, "NM-480101")
    assert result == {"status": "not_determinable"}
    no_doc = tuple(d for d in documents if d.doc_id != "returns-policy")
    assert _call(data_dir, no_doc, EMPLOYEE_STORE7, "NM-480101") == {"status": "not_determinable"}


def test_undeterminable_policy_does_not_unmask_a_denied_order(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    broken = _broken(documents)
    assert _call(data_dir, broken, EMPLOYEE_STORE12, "NM-480101") == NOT_FOUND
    assert _call(data_dir, broken, EMPLOYEE_STORE7, "NM-999999") == NOT_FOUND


def test_every_denial_cause_returns_the_identical_full_dict(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    cases: list[tuple[Principal | None, object]] = [
        (EMPLOYEE_STORE7, "NM-999999"),
        (EMPLOYEE_STORE12, "NM-480101"),
        (REGIONAL_NORTH, "NM-480303"),
        (EMPLOYEE_STORE7, "10x2"),
        (EMPLOYEE_STORE7, "NM-480101 "),
        (EMPLOYEE_STORE7, None),
        (UNKNOWN_ROLE_PRINCIPAL, "NM-480101"),
        (None, "NM-480101"),
    ]
    for principal, order_id in cases:
        assert _call(data_dir, documents, principal, order_id) == NOT_FOUND, (principal, order_id)


def test_throttled_session_gets_the_uniform_denial(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    guard = build_order_guard(data_dir, limit=1)
    state = fake_tool_context(EMPLOYEE_STORE7).state

    def run(order_id: str) -> dict[str, object]:
        return run_check_return_eligibility(
            EligibilityDeps(guard, documents, lambda: TODAY), state, order_id
        )

    assert run("NM-999999") == NOT_FOUND
    assert run("NM-480101") == NOT_FOUND


def test_clock_is_injected_not_read_from_the_system(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    guard = build_order_guard(data_dir)
    state = fake_tool_context(EMPLOYEE_STORE7).state
    late = run_check_return_eligibility(
        EligibilityDeps(guard, documents, lambda: date(2027, 6, 1)), state, "NM-480101"
    )
    assert late["eligible"] is False and late["reason"] == "outside_window"


def test_no_personal_data_in_tool_output_or_logs(
    data_dir: Path, documents: tuple[Document, ...], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    raw = json.loads((data_dir / "orders.json").read_text(encoding="utf-8"))["orders"]
    for entry in raw:
        outputs = [
            _call(data_dir, documents, p, entry["order_id"])
            for p in (EMPLOYEE_STORE7, EMPLOYEE_STORE12, REGIONAL_NORTH, MANAGER_STORE19)
        ]
        outputs.append(_call(data_dir, _broken(documents), EMPLOYEE_STORE7, entry["order_id"]))
        text = json.dumps(outputs) + caplog.text
        for value in entry["customer"].values():
            assert value not in text


def test_unexpected_failure_returns_generic_error_status(
    documents: tuple[Document, ...],
) -> None:
    def boom(_: str) -> None:
        raise RuntimeError("Vanterpool detail")

    guard = OrderGuard(boom, AuditLogger(b"s"), 5)
    state = fake_tool_context(EMPLOYEE_STORE7).state
    result = run_check_return_eligibility(
        EligibilityDeps(guard, documents, lambda: TODAY), state, "NM-480101"
    )
    assert result == {"status": "error"}


def test_tool_signature_and_model_visible_schema_have_no_identity_parameter(
    data_dir: Path, documents: tuple[Document, ...]
) -> None:
    tool = make_check_return_eligibility(build_order_guard(data_dir), documents, lambda: TODAY)
    assert tool.__name__ == "check_return_eligibility"
    assert list(inspect.signature(tool).parameters) == ["order_id", "tool_context"]
    declaration = FunctionTool(tool)._get_declaration()
    assert declaration is not None
    schema = declaration.parameters_json_schema
    assert isinstance(schema, dict) and set(schema["properties"]) == {"order_id"}
    context = FakeToolContext(state=fake_tool_context(EMPLOYEE_STORE7).state)
    assert tool("NM-480101", context)["eligible"] is True
