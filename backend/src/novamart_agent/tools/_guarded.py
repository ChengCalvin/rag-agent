"""Shared by the order tools: one call through the guard (ARCH-MOD-4), private to `tools/`."""

from novamart_agent.models import Order
from novamart_agent.security import OrderGuard, OrderRequest, SessionState


def guarded_order(
    guard: OrderGuard, state: SessionState, tool: str, raw_id: object
) -> Order | None:
    """Return the order only when the guard allows it; None for every denial, whatever the cause.

    The caller maps None to `denied_result()`, so no cause can reach the model.
    """
    access = guard.lookup(state, OrderRequest(tool, raw_id))
    return access.order if access.decision.allowed else None
