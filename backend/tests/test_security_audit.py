"""Task 3.3: before-tool allowlist and the audit log (hashed references, no PII)."""

import json
import logging
from pathlib import Path

import pytest

from fakes import (
    EMPLOYEE_STORE7,
    EMPLOYEE_STORE12,
    REGIONAL_NORTH,
    FakeTool,
    FakeToolContext,
    fake_tool_context,
)
from novamart_agent.adapters import load_orders
from novamart_agent.models import (
    TOOL_CHECK_RETURN_ELIGIBILITY,
    TOOL_GET_ORDER_STATUS,
    TOOL_SEARCH_POLICY,
    Order,
    Principal,
)
from novamart_agent.security import (
    AuditEvent,
    AuditLogger,
    Decision,
    OrderGuard,
    OrderRequest,
    authorize_tool,
    build_audit_record,
    load_principals,
    order_reference,
)
from novamart_agent.security.callbacks import make_before_tool_callback

SALT = b"unit-test-salt"
STORE7_ORDER = "NM-480101"


@pytest.fixture(scope="module")
def orders(data_dir: Path) -> tuple[Order, ...]:
    return load_orders(data_dir / "orders.json")


@pytest.fixture(scope="module")
def personas(data_dir: Path) -> dict[str, Principal]:
    return load_principals(data_dir / "users.json")


def call(callback: object, tool: str, args: dict[str, object], ctx: FakeToolContext) -> object:
    return callback(FakeTool(tool), args, ctx)  # type: ignore[operator]  # callback is typed as object in this helper


def test_before_tool_allows_every_tool_for_known_roles() -> None:
    callback = make_before_tool_callback(AuditLogger(SALT))
    for principal in (EMPLOYEE_STORE7, REGIONAL_NORTH):
        for tool in (TOOL_SEARCH_POLICY, TOOL_GET_ORDER_STATUS, TOOL_CHECK_RETURN_ELIGIBILITY):
            assert call(callback, tool, {}, fake_tool_context(principal)) is None


def test_before_tool_denies_unknown_role_with_the_uniform_result() -> None:
    callback = make_before_tool_callback(AuditLogger(SALT))
    intern = Principal("x", "X", "intern", "store-7", "north")
    for tool in (TOOL_SEARCH_POLICY, TOOL_GET_ORDER_STATUS):
        result = call(callback, tool, {"order_id": STORE7_ORDER}, fake_tool_context(intern))
        assert result == {"status": "not_found"}


def test_before_tool_denies_when_no_identity_and_unknown_tool_names() -> None:
    callback = make_before_tool_callback(AuditLogger(SALT))
    assert call(callback, TOOL_GET_ORDER_STATUS, {}, fake_tool_context(None)) == {
        "status": "not_found"
    }
    assert call(callback, "delete_order", {}, fake_tool_context(EMPLOYEE_STORE7)) == {
        "status": "not_found"
    }
    assert not authorize_tool(EMPLOYEE_STORE7, "delete_order").allowed


def test_before_tool_does_not_mutate_the_model_arguments() -> None:
    callback = make_before_tool_callback(AuditLogger(SALT))
    args: dict[str, object] = {"order_id": STORE7_ORDER}
    call(callback, TOOL_GET_ORDER_STATUS, args, fake_tool_context(EMPLOYEE_STORE7))
    assert args == {"order_id": STORE7_ORDER}


def test_order_reference_is_keyed_stable_and_not_the_id() -> None:
    ref = order_reference(STORE7_ORDER, SALT)
    assert ref == order_reference(STORE7_ORDER, SALT)
    assert ref != order_reference(STORE7_ORDER, b"other-salt")
    assert ref is not None and "480101" not in ref and len(ref) == 16
    assert order_reference(None, SALT) is None


def test_audit_record_has_caller_tool_outcome_and_hashed_reference() -> None:
    record = build_audit_record(
        EMPLOYEE_STORE12,
        AuditEvent("order_access", TOOL_GET_ORDER_STATUS, STORE7_ORDER),
        Decision(False, "out_of_scope"),
        SALT,
    )
    assert (record.caller, record.tool, record.outcome) == (
        "emp_store12",
        TOOL_GET_ORDER_STATUS,
        "denied",
    )
    assert record.order_ref == order_reference(STORE7_ORDER, SALT)


def test_audit_record_fields_are_a_fixed_whitelist() -> None:
    record = build_audit_record(None, AuditEvent("tool_call", "t"), Decision(True, "allowed"), SALT)
    assert set(vars(record)) == {
        "event", "caller", "role", "store_id", "tool", "outcome", "reason", "order_ref"
    }  # fmt: skip
    assert record.caller is None and record.order_ref is None


def test_every_order_tool_call_is_audited_with_allowed_and_denied_outcomes(
    caplog: pytest.LogCaptureFixture, orders: tuple[Order, ...]
) -> None:
    audit = AuditLogger(SALT)
    by_id = {o.order_id: o for o in orders}
    guard = OrderGuard(by_id.get, audit, 5)
    with caplog.at_level(logging.DEBUG):
        ctx = fake_tool_context(EMPLOYEE_STORE12)
        guard.lookup(ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, "NM-480201"))
        guard.lookup(ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, STORE7_ORDER))
    records = [json.loads(r.getMessage().removeprefix("audit ")) for r in caplog.records]
    assert [r["outcome"] for r in records] == ["allowed", "denied"]
    assert [r["reason"] for r in records] == ["allowed", "out_of_scope"]
    assert all(r["order_ref"] and r["caller"] == "emp_store12" for r in records)


def test_seeded_customer_name_email_and_address_never_appear_in_log_output(
    caplog: pytest.LogCaptureFixture,
    orders: tuple[Order, ...],
    personas: dict[str, Principal],
) -> None:
    """Log contents after a lookup: no seeded customer value (or employee name) in any log."""
    audit = AuditLogger(SALT)
    by_id = {o.order_id: o for o in orders}
    guard = OrderGuard(by_id.get, audit, 50)
    callback = make_before_tool_callback(audit)
    seeded = [v for o in orders for v in (o.customer.name, o.customer.email, o.customer.address)]
    seeded += [p.name for p in personas.values()]
    with caplog.at_level(logging.DEBUG):
        for principal in personas.values():
            ctx = fake_tool_context(principal)
            for order in orders:
                args: dict[str, object] = {"order_id": order.order_id}
                call(callback, TOOL_GET_ORDER_STATUS, args, ctx)
                guard.lookup(ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, order.order_id))
            # A model that stuffs customer data into the id argument must not leak it either.
            for pii in seeded[:6]:
                call(callback, TOOL_GET_ORDER_STATUS, {"order_id": pii}, ctx)
                guard.lookup(ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, pii))
    text = "\n".join(r.getMessage() for r in caplog.records) + caplog.text
    assert caplog.records, "the audit logger wrote nothing"
    for value in seeded:
        assert value not in text
    for order in orders:
        assert order.order_id not in text
    local_parts = [o.customer.email.split("@")[0] for o in orders]
    assert not any(part in text for part in local_parts)


def test_audit_goes_through_one_named_logger(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        event = AuditEvent("tool_call", "t")
        AuditLogger(SALT).record(None, event, Decision(False, "no_principal"))
    assert {r.name for r in caplog.records} == {"novamart.audit"}


def test_default_salt_differs_per_logger_instance(caplog: pytest.LogCaptureFixture) -> None:
    event = AuditEvent("tool_call", "t", STORE7_ORDER)
    with caplog.at_level(logging.DEBUG):
        for _ in range(2):
            AuditLogger().record(EMPLOYEE_STORE7, event, Decision(True, "allowed"))
    refs = [json.loads(r.getMessage().removeprefix("audit "))["order_ref"] for r in caplog.records]
    assert refs[0] != refs[1]
