"""Authorization choke point for order data (tasks 3.2, 3.4; ARCH-MOD-4, D3).

Pure logic, no ADK imports (LAYER-3). Every route to an order record goes through
`OrderGuard.lookup`: the id is validated, the order is fetched, then authorized, and the record
is returned only when allowed. Deny by default. Every denial yields the same model-facing result
(`denied_result`), whatever the cause, so denial never reveals existence (ARCH-ERR-1).
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from novamart_agent.models import (
    AUDIENCE_ALL_STAFF,
    AUDIENCE_MANAGER,
    KNOWN_ROLES,
    ROLE_EMPLOYEE,
    ROLE_MANAGER,
    ROLE_REGIONAL_MANAGER,
    STATE_DENIED_LOOKUPS,
    TOOL_CHECK_RETURN_ELIGIBILITY,
    TOOL_GET_ORDER_STATUS,
    TOOL_SEARCH_POLICY,
    TOOL_STATUS_NOT_FOUND,
    Order,
    Principal,
)
from novamart_agent.security.audit import EVENT_ORDER_ACCESS, AuditEvent, AuditLogger
from novamart_agent.security.decision import (
    ALLOW,
    REASON_MALFORMED_ID,
    REASON_NO_PRINCIPAL,
    REASON_NO_SCOPE,
    REASON_NOT_FOUND,
    REASON_OUT_OF_SCOPE,
    REASON_THROTTLED,
    REASON_TOOL_NOT_ALLOWED,
    REASON_UNKNOWN_ROLE,
    Decision,
    deny,
)
from novamart_agent.security.principal import SessionState, principal_from_state

# `NM-` and six ASCII digits (data/README.md). Matched with `fullmatch`, so a trailing newline,
# surrounding spaces or Unicode digits are all malformed.
_ORDER_ID = re.compile(r"NM-[0-9]{6}")

# Which tools each role may call, listed explicitly so a newly added tool is never granted
# automatically (it must be added here and in ROLE_TOOL_DENYLIST by a decision). The spec defines
# no per-role differences today, so every known role gets the same three tools; an unknown role
# gets none (deny by default). Document access is filtered by audience in retrieval, not here.
_BASE_TOOLS: frozenset[str] = frozenset(
    {TOOL_SEARCH_POLICY, TOOL_GET_ORDER_STATUS, TOOL_CHECK_RETURN_ELIGIBILITY}
)
ROLE_TOOL_ALLOWLIST: Mapping[str, frozenset[str]] = {
    ROLE_EMPLOYEE: _BASE_TOOLS,
    ROLE_MANAGER: _BASE_TOOLS,
    ROLE_REGIONAL_MANAGER: _BASE_TOOLS,
}
# Tools a role has been explicitly decided NOT to get. Together with the allowlist this must cover
# every tool name (checked by a test), which forces a decision for each new tool.
ROLE_TOOL_DENYLIST: Mapping[str, frozenset[str]] = {
    ROLE_EMPLOYEE: frozenset(),
    ROLE_MANAGER: frozenset(),
    ROLE_REGIONAL_MANAGER: frozenset(),
}


def parse_order_id(raw: object) -> str | None:
    """Return the order id when it matches the defined format exactly, else None."""
    if isinstance(raw, str) and _ORDER_ID.fullmatch(raw):
        return raw
    return None


def denied_result() -> dict[str, str]:
    """The one model-facing denial, identical for nonexistent, out-of-scope, malformed, unknown
    role and throttled. A fresh dict each call so no caller can mutate a shared one."""
    return {"status": TOOL_STATUS_NOT_FOUND}


def _check_principal(principal: Principal | None) -> Decision:
    if principal is None:
        return deny(REASON_NO_PRINCIPAL)
    if principal.role not in KNOWN_ROLES:
        return deny(REASON_UNKNOWN_ROLE)
    return ALLOW


def authorize_order(principal: Principal | None, order: Order) -> Decision:
    """Decide whether `principal` may see `order`. Deny by default."""
    base = _check_principal(principal)
    if not base.allowed or principal is None:
        return base
    if principal.role in (ROLE_EMPLOYEE, ROLE_MANAGER):
        if principal.store_id is None:
            return deny(REASON_NO_SCOPE)
        return ALLOW if principal.store_id == order.store_id else deny(REASON_OUT_OF_SCOPE)
    if principal.role == ROLE_REGIONAL_MANAGER:
        if principal.region is None:
            return deny(REASON_NO_SCOPE)
        return ALLOW if principal.region == order.region else deny(REASON_OUT_OF_SCOPE)
    return deny(REASON_UNKNOWN_ROLE)  # a known role this function does not handle: deny


def authorize_tool(principal: Principal | None, tool_name: str) -> Decision:
    """Per-role tool allowlist (before-tool callback). Deny by default."""
    base = _check_principal(principal)
    if not base.allowed or principal is None:
        return base
    allowed = ROLE_TOOL_ALLOWLIST.get(principal.role, frozenset())
    return ALLOW if tool_name in allowed else deny(REASON_TOOL_NOT_ALLOWED)


def permitted_audiences(principal: Principal | None) -> frozenset[str]:
    """Document audiences `principal` may retrieve. Deny by default: no principal or an unknown
    role gets none. Managers and regional managers also see manager-only documents."""
    if principal is None:
        return frozenset()
    if principal.role in (ROLE_MANAGER, ROLE_REGIONAL_MANAGER):
        return frozenset({AUDIENCE_ALL_STAFF, AUDIENCE_MANAGER})
    if principal.role == ROLE_EMPLOYEE:
        return frozenset({AUDIENCE_ALL_STAFF})
    return frozenset()


def is_throttled(denied_count: int, limit: int) -> bool:
    """True once a session has had `limit` denied or malformed lookups."""
    return denied_count >= limit


def _count_from_state(state: SessionState) -> int:
    raw = state.get(STATE_DENIED_LOOKUPS)
    return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else 0


@dataclass(frozen=True)
class OrderRequest:
    """One lookup as the tool received it: the tool name and the model-supplied id."""

    tool: str
    raw_order_id: object


@dataclass(frozen=True)
class OrderAccess:
    """Outcome of a guarded lookup. `order` is set only when `decision.allowed`."""

    decision: Decision
    order: Order | None = None


class OrderGuard:
    """The single choke point between the order adapter and a tool result."""

    def __init__(
        self,
        fetch: Callable[[str], Order | None],
        audit: AuditLogger,
        limit: int,
    ) -> None:
        self._fetch = fetch
        self._audit = audit
        self._limit = limit

    def lookup(self, state: SessionState, request: OrderRequest) -> OrderAccess:
        """Validate, fetch, authorize and audit one order lookup for the state's principal.

        Throttled sessions and malformed ids never reach the fetch. Denied and malformed
        lookups raise the session counter, which is kept in session state; allowed lookups do
        not reset it, so interleaving valid lookups cannot defeat the throttle.
        """
        principal = principal_from_state(state)
        count = _count_from_state(state)
        access = self._decide(principal, request, count)
        if not access.decision.allowed:
            state[STATE_DENIED_LOOKUPS] = count + 1
        event = AuditEvent(EVENT_ORDER_ACCESS, request.tool, request.raw_order_id)
        self._audit.record(principal, event, access.decision)
        return access

    def _decide(
        self, principal: Principal | None, request: OrderRequest, count: int
    ) -> OrderAccess:
        if is_throttled(count, self._limit):
            return OrderAccess(deny(REASON_THROTTLED))
        base = _check_principal(principal)
        if not base.allowed:
            return OrderAccess(base)
        order_id = parse_order_id(request.raw_order_id)
        if order_id is None:
            return OrderAccess(deny(REASON_MALFORMED_ID))
        order = self._fetch(order_id)
        if order is None:
            return OrderAccess(deny(REASON_NOT_FOUND))
        decision = authorize_order(principal, order)
        return OrderAccess(decision, order if decision.allowed else None)
