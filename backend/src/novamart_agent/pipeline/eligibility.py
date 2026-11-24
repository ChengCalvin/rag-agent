"""Return-eligibility rule (task 5.2; ARCH-LAYER-3, D5, ARCH-CFG-2).

Pure: no ADK, no I/O, no clock. The reference date is passed in, and every policy parameter
(window, excluded categories, category exceptions, non-returnable conditions) is read from the
returns document's front-matter, never hard-coded. A missing, unreadable or wrongly typed
parameter raises `PolicyParametersError`, so the caller fails closed (`not_determinable`).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from novamart_agent.errors import OrderDataError, PolicyParametersError
from novamart_agent.models import (
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_RETURNED,
    Document,
    Order,
    OrderItem,
)

RETURNS_POLICY_DOC_ID = "returns-policy"

# Sanity ceiling for any return window read from the policy (a year). A larger value is treated
# as a data error (fail closed, `not_determinable`) rather than silently trusted.
MAX_WINDOW_DAYS = 365

REASON_WITHIN_WINDOW = "within_window"
REASON_CATEGORY_EXCEPTION = "category_exception"
REASON_OUTSIDE_WINDOW = "outside_window"
REASON_EXCLUDED_CATEGORY = "excluded_category"
REASON_NON_RETURNABLE_CONDITION = "non_returnable_condition"
REASON_NOT_DELIVERED = "not_delivered"
REASON_ALREADY_RETURNED = "already_returned"


def _norm(value: str) -> str:
    """Canonical form for matching category and condition names: trimmed and case-folded."""
    return value.strip().casefold()



@dataclass(frozen=True)
class CategoryException:
    """A category with its own, shorter or longer, return window."""

    category: str
    window_days: int


@dataclass(frozen=True)
class ReturnPolicy:
    """The return parameters read from the returns document front-matter."""

    document_id: str
    window_days: int
    excluded_categories: tuple[str, ...]
    category_exceptions: tuple[CategoryException, ...]
    non_returnable_conditions: tuple[str, ...]

    def exception_for(self, category: str) -> CategoryException | None:
        """The category exception for `category`, if the policy has one."""
        key = _norm(category)
        return next((e for e in self.category_exceptions if _norm(e.category) == key), None)


@dataclass(frozen=True)
class ItemVerdict:
    """The outcome for one order line. `window_days` is the window that applied, if any."""

    name: str
    category: str
    eligible: bool
    reason: str
    window_days: int | None


@dataclass(frozen=True)
class EligibilityVerdict:
    """The outcome for a whole order: eligible only when every line is. `days_since_delivery`
    is None when the order was not delivered."""

    eligible: bool
    reason: str
    days_since_delivery: int | None
    items: tuple[ItemVerdict, ...]


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_WINDOW_DAYS:
        raise PolicyParametersError(
            f"returns policy: '{field}' must be an integer from 1 to {MAX_WINDOW_DAYS}"
        )
    return value


def _str_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise PolicyParametersError(f"returns policy: '{field}' must be a list of strings")
    return tuple(value)


def _exceptions(value: object) -> tuple[CategoryException, ...]:
    field = "category_exceptions"
    if not isinstance(value, list):
        raise PolicyParametersError(f"returns policy: '{field}' must be a list")
    found: list[CategoryException] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise PolicyParametersError(f"returns policy: '{field}' entries must be objects")
        category = entry.get("category")
        if not isinstance(category, str) or not category.strip():
            raise PolicyParametersError(f"returns policy: '{field}' entry needs a category")
        if any(_norm(e.category) == _norm(category) for e in found):
            raise PolicyParametersError(f"returns policy: '{field}' repeats a category")
        found.append(CategoryException(category, _positive_int(entry.get("window_days"), field)))
    return tuple(found)


def _find_document(documents: tuple[Document, ...]) -> Document:
    for document in documents:
        if document.doc_id == RETURNS_POLICY_DOC_ID:
            return document
    raise PolicyParametersError(f"document '{RETURNS_POLICY_DOC_ID}' is not loaded")


def _policy_from_metadata(document_id: str, meta: Mapping[str, object]) -> ReturnPolicy:
    return ReturnPolicy(
        document_id=document_id,
        window_days=_positive_int(meta.get("return_window_days"), "return_window_days"),
        excluded_categories=_str_tuple(meta.get("excluded_categories"), "excluded_categories"),
        category_exceptions=_exceptions(meta.get("category_exceptions")),
        non_returnable_conditions=_str_tuple(
            meta.get("non_returnable_conditions"), "non_returnable_conditions"
        ),
    )


def load_return_policy(documents: tuple[Document, ...]) -> ReturnPolicy:
    """Read the return parameters from the returns document, or raise `PolicyParametersError`."""
    document = _find_document(documents)
    return _policy_from_metadata(document.doc_id, document.metadata)


def _window_for(policy: ReturnPolicy, category: str) -> int:
    exception = policy.exception_for(category)
    return exception.window_days if exception else policy.window_days


def _item_reason(policy: ReturnPolicy, item: OrderItem, days: int) -> str:
    if _norm(item.category) in {_norm(c) for c in policy.excluded_categories}:
        return REASON_EXCLUDED_CATEGORY
    if _norm(item.condition) in {_norm(c) for c in policy.non_returnable_conditions}:
        return REASON_NON_RETURNABLE_CONDITION
    window = _window_for(policy, item.category)
    if days <= window:
        return REASON_WITHIN_WINDOW
    if days <= policy.window_days:
        return REASON_CATEGORY_EXCEPTION  # past its own shorter window, inside the general one
    return REASON_OUTSIDE_WINDOW


def _item_verdict(policy: ReturnPolicy, item: OrderItem, days: int) -> ItemVerdict:
    reason = _item_reason(policy, item, days)
    excluded = reason in (REASON_EXCLUDED_CATEGORY, REASON_NON_RETURNABLE_CONDITION)
    return ItemVerdict(
        name=item.name,
        category=item.category,
        eligible=reason == REASON_WITHIN_WINDOW,
        reason=reason,
        window_days=None if excluded else _window_for(policy, item.category),
    )


def _days_since_delivery(order: Order, today: date) -> int:
    if order.delivered_date is None or order.delivered_date > today:
        raise OrderDataError("delivered order has no usable delivery date")
    return (today - order.delivered_date).days


def _order_level(reason: str) -> EligibilityVerdict:
    return EligibilityVerdict(False, reason, None, ())


def evaluate_return(order: Order, policy: ReturnPolicy, today: date) -> EligibilityVerdict:
    """Decide whether the order's items may be returned on `today`.

    The window counts whole days from the delivery date, inclusive of the last day. The order is
    eligible only when every line is; the first failing line gives the order's reason.
    """
    if order.status == ORDER_STATUS_RETURNED:
        return _order_level(REASON_ALREADY_RETURNED)
    if order.status != ORDER_STATUS_DELIVERED:
        return _order_level(REASON_NOT_DELIVERED)
    days = _days_since_delivery(order, today)
    if not order.items:
        raise OrderDataError("delivered order has no items")
    items = tuple(_item_verdict(policy, item, days) for item in order.items)
    failing = next((i for i in items if not i.eligible), None)
    if failing is not None:
        return EligibilityVerdict(False, failing.reason, days, items)
    return EligibilityVerdict(True, REASON_WITHIN_WINDOW, days, items)
