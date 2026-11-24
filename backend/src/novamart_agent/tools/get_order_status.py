"""`get_order_status`: the model-facing order status tool (task 5.1, ARCH-LAYER-2).

Thin adapter: the id goes through the guard, and only an allowed order is projected into the
minimised view (status, expected delivery, items). Customer name, email and address are
omitted, not masked (spec: customer data is minimised). Every denial is the one uniform
`denied_result()` (ARCH-ERR-1). It never raises to the model and takes no identity parameter.
"""

import logging
from collections.abc import Callable

from novamart_agent.models import TOOL_GET_ORDER_STATUS, TOOL_STATUS_ERROR, TOOL_STATUS_OK, Order
from novamart_agent.security import OrderGuard, SessionState, denied_result
from novamart_agent.tools._guarded import guarded_order
from novamart_agent.tools._types import Result, ToolContextLike

logger = logging.getLogger(__name__)


def order_status_view(order: Order) -> Result:
    """The minimised view of an allowed order: no customer fields at all."""
    return {
        "status": TOOL_STATUS_OK,
        "order_id": order.order_id,
        "order_status": order.status,
        "expected_delivery": (
            order.expected_delivery.isoformat() if order.expected_delivery else None
        ),
        "items": [{"name": i.name, "quantity": i.quantity} for i in order.items],
    }


def run_get_order_status(guard: OrderGuard, state: SessionState, raw_order_id: object) -> Result:
    """Look up through the guard and map every outcome to a result dict."""
    try:
        order = guarded_order(guard, state, TOOL_GET_ORDER_STATUS, raw_order_id)
        return dict(denied_result()) if order is None else order_status_view(order)
    except Exception as exc:  # the one place unexpected failures become a status
        logger.warning("get_order_status failed: %s", type(exc).__name__)  # class only, no text
        return {"status": TOOL_STATUS_ERROR}


def make_get_order_status(guard: OrderGuard) -> Callable[[str, ToolContextLike], Result]:
    """Build the `get_order_status` tool bound to a guard."""

    def get_order_status(order_id: str, tool_context: ToolContextLike) -> Result:
        """Look up the status of one NovaMart order the caller is allowed to see.

        Args:
            order_id: The order number, in the form NM- followed by six digits.

        Returns:
            status "ok" with order_status, expected_delivery and items (name and
            quantity), or status "not_found" when the order does not exist or is not accessible
            (say exactly that; do not guess why, and do not ask follow-up questions about it).
            Status "error" means the lookup failed; tell the user it is unavailable.
        """
        return run_get_order_status(guard, tool_context.state, order_id)

    return get_order_status
