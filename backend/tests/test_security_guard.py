"""Tasks 3.2 and 3.4: order-id validation, authorization choke point, uniform denial, throttle."""

import dataclasses
import re
from pathlib import Path

import pytest

from fakes import (
    EMPLOYEE_STORE7,
    EMPLOYEE_STORE12,
    MANAGER_STORE7,
    REGIONAL_NORTH,
    UNKNOWN_ROLE_PRINCIPAL,
    FakeTool,
    FakeToolContext,
    fake_tool_context,
)
from novamart_agent import models
from novamart_agent.adapters import load_orders
from novamart_agent.models import (
    ALL_TOOLS,
    KNOWN_ROLES,
    STATE_DENIED_LOOKUPS,
    TOOL_GET_ORDER_STATUS,
    Order,
)
from novamart_agent.security import (
    AuditLogger,
    OrderAccess,
    OrderGuard,
    OrderRequest,
    authorize_order,
    denied_result,
    is_throttled,
    parse_order_id,
    permitted_audiences,
)
from novamart_agent.security.callbacks import make_before_tool_callback
from novamart_agent.security.guard import ROLE_TOOL_ALLOWLIST, ROLE_TOOL_DENYLIST

STORE7_ORDER = "NM-480101"
STORE12_ORDER = "NM-480201"
SOUTH_ORDER = "NM-480301"
MISSING_ORDER = "NM-999999"
LIMIT = 3


@pytest.fixture(scope="module")
def orders(data_dir: Path) -> dict[str, Order]:
    return {o.order_id: o for o in load_orders(data_dir / "orders.json")}


@pytest.fixture
def guard(orders: dict[str, Order]) -> OrderGuard:
    return OrderGuard(orders.get, AuditLogger(b"unit-test-salt"), LIMIT)


def lookup(guard: OrderGuard, ctx: FakeToolContext, raw: object) -> OrderAccess:
    return guard.lookup(ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, raw))


MALFORMED_IDS: list[object] = [
    "",
    "NM-12",
    "NM-4801011",
    "nm-480101",
    "NM480101",
    " NM-480101",
    "NM-480101\n",
    "NM-48010a",
    "NM-٤٨٠١٠١",  # Arabic-Indic digits
    "ORD-480101",
    None,
    480101,
    ["NM-480101"],
]


@pytest.mark.parametrize("raw", MALFORMED_IDS)
def test_malformed_id_is_rejected(raw: object) -> None:
    assert parse_order_id(raw) is None


def test_well_formed_id_is_accepted() -> None:
    assert parse_order_id(STORE7_ORDER) == STORE7_ORDER


def test_malformed_id_rejected_only_in_the_order_tool_without_a_lookup() -> None:
    """Malformed identifier: rejected in the order tool (guard), with no fetch at all."""
    fetched: list[str] = []

    def spy(order_id: str) -> Order | None:
        fetched.append(order_id)
        return None

    ctx = fake_tool_context(EMPLOYEE_STORE7)
    access = OrderGuard(spy, AuditLogger(b"t"), LIMIT).lookup(
        ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, "NM-12")
    )
    assert not access.decision.allowed and access.order is None
    assert fetched == []


def test_intake_and_precheck_never_reject_or_reroute_an_order_id() -> None:
    """Malformed identifier: validation lives only in security/guard, never in pipeline/agents."""
    src = Path(__file__).resolve().parent.parent / "src" / "novamart_agent"
    for package in ("pipeline", "agents", "prompts"):
        for path in (src / package).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"NM-\[|parse_order_id|order_id", text), path.name


def test_cross_store_request(guard: OrderGuard) -> None:
    """Scenario 'Cross-store request': a store-12 employee asking for a store-7 order is denied."""
    access = lookup(guard, fake_tool_context(EMPLOYEE_STORE12), STORE7_ORDER)
    assert not access.decision.allowed and access.order is None


def test_own_store_request_is_allowed(guard: OrderGuard, orders: dict[str, Order]) -> None:
    access = lookup(guard, fake_tool_context(EMPLOYEE_STORE7), STORE7_ORDER)
    assert access.decision.allowed and access.order == orders[STORE7_ORDER]
    assert lookup(guard, fake_tool_context(MANAGER_STORE7), STORE7_ORDER).decision.allowed


def test_regional_manager_allow(guard: OrderGuard) -> None:
    """Scenario 'Regional manager': any store in their region is allowed."""
    ctx = fake_tool_context(REGIONAL_NORTH)
    assert lookup(guard, ctx, STORE7_ORDER).decision.allowed
    assert lookup(guard, ctx, STORE12_ORDER).decision.allowed


def test_regional_manager_denied_outside_their_region(guard: OrderGuard) -> None:
    access = lookup(guard, fake_tool_context(REGIONAL_NORTH), SOUTH_ORDER)
    assert not access.decision.allowed and access.order is None


def test_unknown_role_deny(guard: OrderGuard) -> None:
    intern = dataclasses.replace(EMPLOYEE_STORE7, role="intern")
    access = lookup(guard, fake_tool_context(intern), STORE7_ORDER)
    assert not access.decision.allowed and access.decision.reason == "unknown_role"


@pytest.mark.parametrize("role", ["employee", "manager"])
def test_store_less_employee_or_manager_is_denied(guard: OrderGuard, role: str) -> None:
    principal = dataclasses.replace(EMPLOYEE_STORE7, role=role, store_id=None)
    assert not lookup(guard, fake_tool_context(principal), STORE7_ORDER).decision.allowed


def test_region_less_regional_manager_is_denied(guard: OrderGuard) -> None:
    principal = dataclasses.replace(REGIONAL_NORTH, region=None)
    assert not lookup(guard, fake_tool_context(principal), STORE7_ORDER).decision.allowed


@pytest.mark.parametrize("identity", [None, "emp_store7", [], {}, {"role": "employee"}])
def test_missing_or_malformed_identity_is_denied(guard: OrderGuard, identity: object) -> None:
    ctx = FakeToolContext(state={"principal": identity})
    access = lookup(guard, ctx, STORE7_ORDER)
    assert not access.decision.allowed and access.order is None


def test_authorize_order_denies_when_principal_is_none(orders: dict[str, Order]) -> None:
    assert not authorize_order(None, orders[STORE7_ORDER]).allowed


def test_identical_denial_vs_not_found(guard: OrderGuard) -> None:
    """Scenario 'Nonexistent vs unauthorized': both give the same model-facing result."""
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    forbidden = lookup(guard, ctx, STORE7_ORDER)
    missing = lookup(guard, ctx, MISSING_ORDER)
    malformed = lookup(guard, ctx, "NM-12")
    assert not forbidden.decision.allowed and not missing.decision.allowed
    assert forbidden.decision.reason != missing.decision.reason  # audit keeps the true reason
    assert forbidden.order is None and missing.order is None and malformed.order is None
    assert denied_result() == {"status": "not_found"}


def test_denied_results_are_independent_objects() -> None:
    first = denied_result()
    first["status"] = "changed"
    assert denied_result() == {"status": "not_found"}


def test_sequential_identifier_probing_throttled(guard: OrderGuard) -> None:
    """Scenario 'Sequential probing': after the limit of denied lookups, everything is denied."""
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    for i in range(LIMIT):
        assert lookup(guard, ctx, f"NM-48010{i}").decision.reason != "throttled"
    assert lookup(guard, ctx, STORE12_ORDER).decision.reason == "throttled"
    assert ctx.state[STATE_DENIED_LOOKUPS] == LIMIT + 1


def test_throttled_session_returns_nothing_even_for_its_own_orders(guard: OrderGuard) -> None:
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    for _ in range(LIMIT):
        lookup(guard, ctx, "NM-12")
    access = lookup(guard, ctx, STORE12_ORDER)
    assert not access.decision.allowed and access.order is None


def test_throttled_lookup_never_reaches_the_order_adapter(orders: dict[str, Order]) -> None:
    fetched: list[str] = []

    def spy(order_id: str) -> Order | None:
        fetched.append(order_id)
        return orders.get(order_id)

    spy_guard = OrderGuard(spy, AuditLogger(b"t"), LIMIT)
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    for _ in range(LIMIT):
        lookup(spy_guard, ctx, "NM-12")
    lookup(spy_guard, ctx, STORE12_ORDER)
    assert fetched == []


def test_allowed_lookups_do_not_reset_the_denied_counter(guard: OrderGuard) -> None:
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    lookup(guard, ctx, "NM-12")
    lookup(guard, ctx, STORE12_ORDER)
    assert ctx.state[STATE_DENIED_LOOKUPS] == 1


def test_throttle_is_per_session_state(guard: OrderGuard) -> None:
    throttled = fake_tool_context(EMPLOYEE_STORE12)
    for _ in range(LIMIT):
        lookup(guard, throttled, "NM-12")
    fresh = fake_tool_context(EMPLOYEE_STORE12)
    assert lookup(guard, fresh, STORE12_ORDER).decision.allowed


def test_is_throttled_boundary() -> None:
    assert not is_throttled(LIMIT - 1, LIMIT)
    assert is_throttled(LIMIT, LIMIT)


def test_guard_result_carries_no_order_on_denial(guard: OrderGuard) -> None:
    access = lookup(guard, fake_tool_context(EMPLOYEE_STORE12), STORE7_ORDER)
    assert access.order is None and not access.decision.allowed


LONE_SURROGATE_IDS = ["\ud800", "NM-\udc00\ud800", "\ud83d"]


@pytest.mark.parametrize("raw", LONE_SURROGATE_IDS)
def test_lone_surrogate_id_gets_the_uniform_denial_from_the_guard(
    guard: OrderGuard, raw: str
) -> None:
    access = lookup(guard, fake_tool_context(EMPLOYEE_STORE7), raw)
    plain = lookup(guard, fake_tool_context(EMPLOYEE_STORE7), "NM-12")
    assert not access.decision.allowed and access.order is None
    assert access.decision == plain.decision


@pytest.mark.parametrize("raw", LONE_SURROGATE_IDS)
def test_lone_surrogate_id_gets_the_uniform_denial_from_the_before_tool_callback(
    raw: str,
) -> None:
    """Same result as any other denial (no identity), and nothing raises."""
    callback = make_before_tool_callback(AuditLogger(b"t"))
    ctx = fake_tool_context(None)  # no identity: every call is denied
    tool = FakeTool(TOOL_GET_ORDER_STATUS)
    result = callback(tool, {"order_id": raw}, ctx)  # type: ignore[arg-type]  # test doubles
    other = callback(tool, {"order_id": "NM-12"}, ctx)  # type: ignore[arg-type]  # test doubles
    assert result == other == denied_result()


def test_every_tool_has_an_explicit_decision_for_every_known_role() -> None:
    """A tool added to the constants but not decided per role is not granted automatically."""
    declared = {
        value
        for name, value in vars(models).items()
        if name.startswith("TOOL_") and not name.startswith("TOOL_STATUS_")
    }
    assert declared == set(ALL_TOOLS)
    assert set(ROLE_TOOL_ALLOWLIST) == set(KNOWN_ROLES) == set(ROLE_TOOL_DENYLIST)
    for role in KNOWN_ROLES:
        allowed, denied = ROLE_TOOL_ALLOWLIST[role], ROLE_TOOL_DENYLIST[role]
        assert not allowed & denied
        assert allowed | denied == ALL_TOOLS, f"undecided tools for {role}"


# --- QA audit additions: strengthen the rebuilt file against the spec scenarios ---

HOSTILE_IDS: list[object] = [
    "NM-480101\x00",
    "NM-48\x000101",
    "\nNM-480101",
    "NM-480101 ",
    "NM-４８０１０１",  # fullwidth digits
    "NM‑480101",  # non-breaking hyphen
    "Nm-480101",
    "NM-48010",
    b"NM-480101",
    {"order_id": "NM-480101"},
    True,
]


class _LooksLikeAnId:
    """A non-string whose str() is a valid id: coercion before matching would accept it."""

    def __str__(self) -> str:
        return STORE7_ORDER


@pytest.mark.parametrize("raw", [*MALFORMED_IDS, *HOSTILE_IDS, _LooksLikeAnId()])
def test_every_malformed_id_is_rejected_by_the_guard_without_a_fetch(raw: object) -> None:
    """Scenario 'Malformed identifier': malformed_id, no order lookup, and the counter rises."""
    fetched: list[str] = []

    def spy(order_id: str) -> Order | None:
        fetched.append(order_id)
        return None

    ctx = fake_tool_context(EMPLOYEE_STORE7)
    access = OrderGuard(spy, AuditLogger(b"t"), LIMIT).lookup(
        ctx.state, OrderRequest(TOOL_GET_ORDER_STATUS, raw)
    )
    assert access.decision.reason == "malformed_id"
    assert not access.decision.allowed and access.order is None
    assert fetched == []
    assert ctx.state[STATE_DENIED_LOOKUPS] == 1


@pytest.mark.parametrize("raw", HOSTILE_IDS)
def test_hostile_ids_fail_parse_order_id(raw: object) -> None:
    assert parse_order_id(raw) is None


@pytest.mark.parametrize("role", ["employee", "manager"])
def test_store_less_employee_or_manager_is_denied_for_lack_of_scope(
    guard: OrderGuard, role: str
) -> None:
    principal = dataclasses.replace(EMPLOYEE_STORE7, role=role, store_id=None)
    access = lookup(guard, fake_tool_context(principal), STORE7_ORDER)
    assert access.decision.reason == "no_scope" and access.order is None


def test_region_less_regional_manager_is_denied_for_lack_of_scope(guard: OrderGuard) -> None:
    principal = dataclasses.replace(REGIONAL_NORTH, region=None)
    access = lookup(guard, fake_tool_context(principal), STORE7_ORDER)
    assert access.decision.reason == "no_scope" and access.order is None


def test_regional_manager_scope_is_exactly_their_region(
    guard: OrderGuard, orders: dict[str, Order]
) -> None:
    for order in orders.values():
        access = lookup(guard, fake_tool_context(REGIONAL_NORTH), order.order_id)
        assert access.decision.allowed == (order.region == "north"), order.order_id
        assert (access.order is not None) == access.decision.allowed


def test_store_scoped_roles_see_exactly_their_own_store(
    guard: OrderGuard, orders: dict[str, Order]
) -> None:
    for principal in (EMPLOYEE_STORE7, MANAGER_STORE7, EMPLOYEE_STORE12):
        for order in orders.values():
            access = lookup(guard, fake_tool_context(principal), order.order_id)
            assert access.decision.allowed == (order.store_id == principal.store_id)
            assert (access.order is not None) == access.decision.allowed


@pytest.mark.parametrize("role", ["intern", "", "EMPLOYEE", "admin", " employee", "superadmin"])
def test_unknown_roles_get_nothing_for_any_order(guard: OrderGuard, role: str) -> None:
    principal = dataclasses.replace(REGIONAL_NORTH, role=role, store_id="store-7")
    for order_id in (STORE7_ORDER, STORE12_ORDER, SOUTH_ORDER):
        access = lookup(guard, fake_tool_context(principal), order_id)
        assert access.decision.reason == "unknown_role" and access.order is None


def test_every_denial_cause_gives_the_same_model_facing_dict() -> None:
    """Scenario 'Compare denial and nonexistent order': full-dict equality across all causes.

    The guard reports different internal reasons; the model-facing dict comes from
    `denied_result` and the before-tool callback, and must not vary by cause.
    """
    callback = make_before_tool_callback(AuditLogger(b"t"))
    intern = dataclasses.replace(EMPLOYEE_STORE7, role="intern")
    results = [
        callback(
            FakeTool(TOOL_GET_ORDER_STATUS), {"order_id": STORE7_ORDER}, fake_tool_context(None)
        ),
        callback(
            FakeTool(TOOL_GET_ORDER_STATUS), {"order_id": MISSING_ORDER}, fake_tool_context(None)
        ),
        callback(FakeTool(TOOL_GET_ORDER_STATUS), {"order_id": "NM-12"}, fake_tool_context(intern)),
        callback(
            FakeTool("delete_order"), {"order_id": STORE7_ORDER}, fake_tool_context(EMPLOYEE_STORE7)
        ),
        callback(FakeTool(""), {}, fake_tool_context(EMPLOYEE_STORE7)),
    ]  # type: ignore[arg-type]
    assert all(r == denied_result() == {"status": "not_found"} for r in results)
    assert all(r is not results[0] for r in results[1:])


def test_denial_reasons_differ_only_internally_and_none_carries_data(
    orders: dict[str, Order],
) -> None:
    """Out-of-scope, nonexistent, malformed, unknown role, no principal, throttled."""
    guard = OrderGuard(orders.get, AuditLogger(b"t"), LIMIT)
    intern = dataclasses.replace(EMPLOYEE_STORE7, role="intern")
    cases = [
        (EMPLOYEE_STORE12, STORE7_ORDER),
        (EMPLOYEE_STORE12, MISSING_ORDER),
        (EMPLOYEE_STORE12, "NM-12"),
        (intern, STORE7_ORDER),
        (None, STORE7_ORDER),
    ]
    reasons = set()
    for principal, raw in cases:
        access = lookup(guard, fake_tool_context(principal), raw)
        assert not access.decision.allowed and access.order is None
        reasons.add(access.decision.reason)
    assert len(reasons) == len(cases)


def test_interleaved_allowed_lookups_cannot_defeat_the_throttle(guard: OrderGuard) -> None:
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    for i in range(LIMIT):
        assert lookup(guard, ctx, STORE12_ORDER).decision.allowed  # an allowed lookup between
        assert lookup(guard, ctx, f"NM-48010{i}").decision.reason != "throttled"
    assert ctx.state[STATE_DENIED_LOOKUPS] == LIMIT
    after = lookup(guard, ctx, STORE12_ORDER)
    assert after.decision.reason == "throttled" and after.order is None


def test_throttle_counts_every_denial_cause_toward_the_limit(guard: OrderGuard) -> None:
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    for raw in (STORE7_ORDER, MISSING_ORDER, "garbage"):  # out of scope, not found, malformed
        assert lookup(guard, ctx, raw).decision.reason != "throttled"
    assert lookup(guard, ctx, STORE12_ORDER).decision.reason == "throttled"


def test_throttle_is_per_session_for_a_second_probing_session(guard: OrderGuard) -> None:
    a = fake_tool_context(EMPLOYEE_STORE12)
    b = fake_tool_context(EMPLOYEE_STORE12)
    for _ in range(LIMIT):
        lookup(guard, a, "NM-12")
    assert lookup(guard, a, STORE12_ORDER).decision.reason == "throttled"
    assert lookup(guard, b, "NM-12").decision.reason == "malformed_id"
    assert b.state[STATE_DENIED_LOOKUPS] == 1
    assert a.state[STATE_DENIED_LOOKUPS] == LIMIT + 1


@pytest.mark.parametrize("forged", [-5, True, "7", 2.5, None])
def test_a_forged_counter_in_state_is_not_a_bypass_or_a_crash(
    guard: OrderGuard, forged: object
) -> None:
    ctx = fake_tool_context(EMPLOYEE_STORE12)
    ctx.state[STATE_DENIED_LOOKUPS] = forged
    assert lookup(guard, ctx, STORE7_ORDER).decision.reason == "out_of_scope"
    assert ctx.state[STATE_DENIED_LOOKUPS] == 1


@pytest.mark.parametrize(
    ("principal", "expected"),
    [
        (EMPLOYEE_STORE7, {"all_staff"}),
        (MANAGER_STORE7, {"all_staff", "manager"}),
        (REGIONAL_NORTH, {"all_staff", "manager"}),
        (UNKNOWN_ROLE_PRINCIPAL, set()),
        (None, set()),
    ],
)
def test_permitted_audiences_per_role_denies_by_default(
    principal: models.Principal | None, expected: set[str]
) -> None:
    assert permitted_audiences(principal) == frozenset(expected)
