"""Task 5.1: `get_order_status` returns the minimised view; denial is uniform (Spec: "Permitted
order", "Unknown order", "Malformed identifier", "Order lookup output", "Order tools are
read-only").
"""

import inspect
import json
import logging
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
from novamart_agent.adapters import OrdersApi
from novamart_agent.models import Principal
from novamart_agent.security import AuditLogger, OrderGuard
from novamart_agent.tools import make_get_order_status, run_get_order_status

NOT_FOUND = {"status": "not_found"}


@pytest.fixture
def guard(data_dir: Path) -> OrderGuard:
    return build_order_guard(data_dir)


def _call(guard: OrderGuard, principal: Principal | None, order_id: object) -> dict[str, object]:
    return run_get_order_status(guard, fake_tool_context(principal).state, order_id)


def test_permitted_order_reports_status_expected_delivery_and_items(guard: OrderGuard) -> None:
    result = _call(guard, EMPLOYEE_STORE7, "NM-480103")  # in transit, own store
    assert result["status"] == "ok" and result["order_status"] == "in_transit"
    assert result["expected_delivery"] is not None
    items = result["items"]
    assert isinstance(items, list) and items and set(items[0]) == {"name", "quantity"}
    assert set(result) == {
        "status",
        "order_id",
        "order_status",
        "expected_delivery",
        "items",
    }


def test_regional_manager_sees_an_order_in_the_region(guard: OrderGuard) -> None:
    assert _call(guard, REGIONAL_NORTH, "NM-480203")["status"] == "ok"


def test_every_denial_cause_returns_the_identical_full_dict(data_dir: Path) -> None:
    cases: list[tuple[Principal | None, object]] = [
        (EMPLOYEE_STORE7, "NM-999999"),  # nonexistent
        (EMPLOYEE_STORE12, "NM-480103"),  # out of scope: another store
        (EMPLOYEE_STORE7, "NM-480303"),  # out of scope: another region
        (REGIONAL_NORTH, "NM-480303"),  # out of scope for a regional manager
        (EMPLOYEE_STORE7, "10x2"),  # malformed
        (EMPLOYEE_STORE7, "NM-480103\n"),  # malformed: trailing newline
        (EMPLOYEE_STORE7, None),  # malformed: not a string
        (EMPLOYEE_STORE7, 480103),  # malformed: not a string
        (UNKNOWN_ROLE_PRINCIPAL, "NM-480103"),  # unknown role
        (None, "NM-480103"),  # no principal
    ]
    for principal, order_id in cases:
        result = _call(build_order_guard(data_dir), principal, order_id)
        assert result == NOT_FOUND, (principal, order_id)
        assert list(result) == ["status"]


def test_throttled_session_returns_the_same_dict_even_for_a_permitted_order(
    data_dir: Path,
) -> None:
    guard = build_order_guard(data_dir, limit=2)
    context = fake_tool_context(EMPLOYEE_STORE7)
    for _ in range(2):
        assert run_get_order_status(guard, context.state, "NM-999999") == NOT_FOUND
    assert run_get_order_status(guard, context.state, "NM-480103") == NOT_FOUND


def test_malformed_id_never_reaches_the_order_backend(data_dir: Path) -> None:
    backend = OrdersApi.from_file(data_dir / "orders.json")
    seen: list[str] = []

    def spy(order_id: str) -> object:
        seen.append(order_id)
        return backend.get(order_id)

    guard = OrderGuard(spy, AuditLogger(b"s"), 5)  # type: ignore[arg-type]  # spy returns Order|None
    assert _call(guard, EMPLOYEE_STORE7, "10x2") == NOT_FOUND
    assert seen == []


def test_no_customer_name_email_or_address_in_any_tool_output(
    data_dir: Path, guard: OrderGuard
) -> None:
    raw = json.loads((data_dir / "orders.json").read_text(encoding="utf-8"))["orders"]
    for entry in raw:
        outputs = [
            _call(build_order_guard(data_dir), principal, entry["order_id"])
            for principal in (EMPLOYEE_STORE7, EMPLOYEE_STORE12, REGIONAL_NORTH)
        ]
        text = json.dumps(outputs)
        customer = entry["customer"]
        for value in (customer["name"], customer["email"], customer["address"]):
            assert value not in text
        assert "@" not in text and "ZZ" not in text


def test_seeded_personal_data_never_appears_in_logs(
    data_dir: Path, guard: OrderGuard, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _call(guard, EMPLOYEE_STORE7, "NM-480103")
    _call(guard, EMPLOYEE_STORE12, "NM-480103")
    _call(guard, EMPLOYEE_STORE7, "NM-000000")
    raw = json.loads((data_dir / "orders.json").read_text(encoding="utf-8"))["orders"]
    for entry in raw:
        for value in entry["customer"].values():
            assert value not in caplog.text


def test_unexpected_failure_returns_generic_error_status_without_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def boom(_: str) -> None:
        raise RuntimeError("Vanterpool secret detail")

    guard = OrderGuard(boom, AuditLogger(b"s"), 5)
    result = _call(guard, EMPLOYEE_STORE7, "NM-480103")
    assert result == {"status": "error"}
    assert "Vanterpool" not in caplog.text


def test_order_backend_is_read_only(data_dir: Path) -> None:
    backend = OrdersApi.from_file(data_dir / "orders.json")
    public = {n for n in dir(backend) if not n.startswith("_")}
    assert public == {"get", "from_file"}
    assert backend.get("NM-480103") is not None and backend.get("NM-000000") is None


def test_tool_signature_and_model_visible_schema_have_no_identity_parameter(
    guard: OrderGuard,
) -> None:
    tool = make_get_order_status(guard)
    assert tool.__name__ == "get_order_status"
    assert list(inspect.signature(tool).parameters) == ["order_id", "tool_context"]
    declaration = FunctionTool(tool)._get_declaration()
    assert declaration is not None
    schema = declaration.parameters_json_schema
    assert isinstance(schema, dict) and set(schema["properties"]) == {"order_id"}
    context = FakeToolContext(state=fake_tool_context(EMPLOYEE_STORE7).state)
    assert tool("NM-480103", context)["status"] == "ok"
    assert tool("NM-480102", context)["status"] == "ok"
    assert tool("NM-480201", context) == NOT_FOUND
