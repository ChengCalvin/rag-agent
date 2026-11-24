"""Typed models shared across layers (LAYER-4, ARCH-LAYER-4).

Pure data: no I/O. Customer contact fields are excluded from `repr` so an accidental
`repr(order)` in a log line cannot leak personal data (ERR-2).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

DOC_TYPES: frozenset[str] = frozenset({"policy", "product"})
AUDIENCE_ALL_STAFF = "all_staff"
AUDIENCE_MANAGER = "manager"
AUDIENCES: frozenset[str] = frozenset({AUDIENCE_ALL_STAFF, AUDIENCE_MANAGER})

ROLE_EMPLOYEE = "employee"
ROLE_MANAGER = "manager"
ROLE_REGIONAL_MANAGER = "regional_manager"
KNOWN_ROLES: frozenset[str] = frozenset({ROLE_EMPLOYEE, ROLE_MANAGER, ROLE_REGIONAL_MANAGER})

# Tool result statuses (ARCH-ERR-1). `no_answer` belongs to retrieval (chunk 4).
TOOL_STATUS_OK = "ok"
TOOL_STATUS_NOT_FOUND = "not_found"
TOOL_STATUS_NO_ANSWER = "no_answer"
# The generic failure status for an unexpected exception (ARCH-ERR-1); never a model-facing detail.
TOOL_STATUS_ERROR = "error"
# Return eligibility could not be decided (policy parameters unusable); fail closed (D13 case F).
TOOL_STATUS_NOT_DETERMINABLE = "not_determinable"

# Tool names the model sees (ARCH-MOD-3: equal to the function names).
TOOL_SEARCH_POLICY = "search_policy"
TOOL_GET_ORDER_STATUS = "get_order_status"
TOOL_CHECK_RETURN_ELIGIBILITY = "check_return_eligibility"
ORDER_TOOLS: frozenset[str] = frozenset({TOOL_GET_ORDER_STATUS, TOOL_CHECK_RETURN_ELIGIBILITY})
ALL_TOOLS: frozenset[str] = ORDER_TOOLS | {TOOL_SEARCH_POLICY}

# Session-state keys. Plain names (no `user:`/`app:`/`temp:` prefix): session-scoped and persisted.
STATE_PRINCIPAL = "principal"
STATE_DENIED_LOOKUPS = "denied_lookups"

ORDER_STATUS_DELIVERED = "delivered"
ORDER_STATUS_IN_TRANSIT = "in_transit"
ORDER_STATUS_RETURNED = "returned"
ORDER_STATUSES: frozenset[str] = frozenset(
    {ORDER_STATUS_DELIVERED, ORDER_STATUS_IN_TRANSIT, ORDER_STATUS_RETURNED}
)


@dataclass(frozen=True)
class Document:
    """One knowledge document: parsed front-matter plus the markdown body."""

    doc_id: str
    title: str
    doc_type: str
    audience: str
    path: Path
    body: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """One retrievable section of a document, carrying what citations and filters need."""

    chunk_id: str
    doc_id: str
    title: str
    heading: str
    path: Path
    doc_type: str
    audience: str
    text: str


@dataclass(frozen=True)
class Principal:
    """The caller: established by the application, never by the model (ARCH-BOUND-1 c).

    `role` is a plain string on purpose: an unknown role must reach the authorization
    function and be denied there (deny by default), not fail at load time.
    """

    user_id: str
    name: str
    role: str
    store_id: str | None
    region: str | None


@dataclass(frozen=True)
class Customer:
    """Seeded synthetic customer. Never logged (ERR-2)."""

    name: str = field(repr=False)
    email: str = field(repr=False)
    address: str = field(repr=False)


@dataclass(frozen=True)
class OrderItem:
    """One order line."""

    sku: str
    name: str
    category: str
    quantity: int
    condition: str


@dataclass(frozen=True)
class Order:
    """One order record as held by the order system stub."""

    order_id: str
    store_id: str
    region: str
    status: str
    ordered_date: date
    expected_delivery: date | None
    delivered_date: date | None
    returned_date: date | None
    customer: Customer
    items: tuple[OrderItem, ...]


class Route(StrEnum):
    """The route an intake rubric asks for (design D10)."""

    ORDER = "order"
    KNOWLEDGE = "knowledge"
    CLARIFY = "clarify"
    OOS = "oos"


class ConfidenceBand(StrEnum):
    """The band shown to the user instead of a number (design D12)."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True)
class Criterion:
    """One checkable part of the user's intent.

    `unanswered_policy` is set by intake on an order-route rubric for a policy part that the
    order path cannot answer (design D14); code then appends the fixed limitation sentence.
    """

    text: str
    required: bool
    unanswered_policy: bool = False


@dataclass(frozen=True)
class Rubric:
    """Intake output, parsed once from untrusted model output (ARCH-BOUND-1 b)."""

    route: Route
    doc_type: str | None
    criteria: tuple[Criterion, ...]
    missing_slots: tuple[str, ...] = ()

    @property
    def flags_unanswered_policy(self) -> bool:
        """True when intake marked a policy criterion that the order path cannot answer."""
        return any(c.unanswered_policy for c in self.criteria)


@dataclass(frozen=True)
class Verdict:
    """Validator output, parsed once from untrusted model output (ARCH-BOUND-1 b).

    `covered` has exactly one entry per rubric criterion, in order. Quotes the validator gives
    as evidence are deliberately not kept: nothing downstream needs them.
    """

    covered: tuple[bool, ...]
    llm_confidence: float
    rewritten_query: str | None


@dataclass(frozen=True)
class RetrievedChunk:
    """One chunk of a `search_policy` result, as the model-facing result dict carries it."""

    document_id: str
    heading: str
    file_name: str
    doc_type: str
    text: str
    score: float


@dataclass(frozen=True)
class DocumentRef:
    """What a citation needs from a document: its title and file name (no section heading)."""

    title: str
    file_name: str


@dataclass(frozen=True)
class SourceEntry:
    """One line of the Sources list. `heading` is None on the order route (design D15)."""

    title: str
    path: str
    heading: str | None = None
