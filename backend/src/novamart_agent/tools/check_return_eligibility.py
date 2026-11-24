"""`check_return_eligibility`: deterministic return eligibility (task 5.2, D5, ARCH-LAYER-2).

Thin adapter: the id goes through the guard first, so a denied order gets the identical
`denied_result()` whatever the policy state. Only then are the return parameters read from the
returns document and the pure rule in `pipeline/eligibility` applied on the injected date.
Missing or unreadable parameters give `{"status": "not_determinable"}` (D13 case F, fail closed),
which the orchestrator turns into canned wording plus the escalation contact. The result carries
`policy_document_id` and `parameters_used` as structured fields for the Sources entry (AG-41).
Never raises to the model; no identity parameter.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from novamart_agent.errors import EligibilityError
from novamart_agent.models import (
    TOOL_CHECK_RETURN_ELIGIBILITY,
    TOOL_STATUS_ERROR,
    TOOL_STATUS_NOT_DETERMINABLE,
    TOOL_STATUS_OK,
    Document,
    Order,
)
from novamart_agent.pipeline import (
    EligibilityVerdict,
    ItemVerdict,
    ReturnPolicy,
    evaluate_return,
    load_return_policy,
)
from novamart_agent.security import OrderGuard, SessionState, denied_result
from novamart_agent.tools._guarded import guarded_order
from novamart_agent.tools._types import Result, ToolContextLike

logger = logging.getLogger(__name__)

Clock = Callable[[], date]


def _parameters_used(policy: ReturnPolicy) -> Result:
    return {
        "return_window_days": policy.window_days,
        "excluded_categories": list(policy.excluded_categories),
        "category_exceptions": [
            {"category": e.category, "window_days": e.window_days}
            for e in policy.category_exceptions
        ],
        "non_returnable_conditions": list(policy.non_returnable_conditions),
    }


def _item_result(item: ItemVerdict) -> Result:
    return {
        "name": item.name,
        "category": item.category,
        "eligible": item.eligible,
        "reason": item.reason,
        "window_days": item.window_days,
    }


def eligibility_result(
    order: Order, policy: ReturnPolicy, verdict: EligibilityVerdict, today: date
) -> Result:
    """The model-facing success result: the verdict, the cited policy and the parameters used."""
    return {
        "status": TOOL_STATUS_OK,
        "order_id": order.order_id,
        "eligible": verdict.eligible,
        "reason": verdict.reason,
        "policy_document_id": policy.document_id,
        "parameters_used": _parameters_used(policy),
        "reference_date": today.isoformat(),
        "days_since_delivery": verdict.days_since_delivery,
        "items": [_item_result(i) for i in verdict.items],
    }


@dataclass(frozen=True)
class EligibilityDeps:
    """What the tool is bound to: the guard, the loaded documents and the clock."""

    guard: OrderGuard
    documents: tuple[Document, ...]
    today: Clock


def run_check_return_eligibility(
    deps: EligibilityDeps, state: SessionState, raw_order_id: object
) -> Result:
    """Guard first, then the rule; map every outcome to a result dict."""
    try:
        order = guarded_order(deps.guard, state, TOOL_CHECK_RETURN_ELIGIBILITY, raw_order_id)
        if order is None:
            return dict(denied_result())
        reference = deps.today()
        policy = load_return_policy(deps.documents)
        verdict = evaluate_return(order, policy, reference)
        return eligibility_result(order, policy, verdict, reference)
    except EligibilityError as exc:  # parameters or order dates unusable: fail closed
        logger.warning("check_return_eligibility undeterminable: %s", type(exc).__name__)
        return {"status": TOOL_STATUS_NOT_DETERMINABLE}
    except Exception as exc:  # the one place unexpected failures become a status
        logger.warning("check_return_eligibility failed: %s", type(exc).__name__)
        return {"status": TOOL_STATUS_ERROR}


def make_check_return_eligibility(
    guard: OrderGuard,
    documents: tuple[Document, ...],
    today: Clock = date.today,
) -> Callable[[str, ToolContextLike], Result]:
    """Build the tool bound to a guard, the loaded documents and a clock (tests inject a date)."""

    deps = EligibilityDeps(guard, documents, today)

    def check_return_eligibility(order_id: str, tool_context: ToolContextLike) -> Result:
        """Decide whether the items of one NovaMart order can be returned, from policy rules.

        Args:
            order_id: The order number, in the form NM- followed by six digits.

        Returns:
            status "ok" with eligible (true or false), a reason code, the policy_document_id
            and parameters_used (explain the outcome from these, never from memory); status
            "not_found" when the order does not exist or is not accessible (say exactly that);
            status "not_determinable" when the return policy could not be read (say eligibility
            cannot be determined and nothing more); status "error" when the check failed.
        """
        return run_check_return_eligibility(deps, tool_context.state, order_id)

    return check_return_eligibility
