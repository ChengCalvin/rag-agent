"""Audit record builder and the single audit logger (task 3.3; ARCH-EDGE-1, ERR-2).

PII hygiene is by construction: a record holds only whitelisted fields (caller id, role, store,
tool, event, outcome, reason) and a keyed hash of the order reference. Customer names, emails,
addresses, employee names, message text and raw tool arguments never enter it. No ADK imports.
"""

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import asdict, dataclass

from novamart_agent.models import Principal
from novamart_agent.security.decision import Decision

AUDIT_LOGGER_NAME = "novamart.audit"

EVENT_TOOL_CALL = "tool_call"  # before-tool callback: per-role allowlist
EVENT_ORDER_ACCESS = "order_access"  # guard: the true lookup outcome

OUTCOME_ALLOWED = "allowed"
OUTCOME_DENIED = "denied"

_REF_LENGTH = 16


@dataclass(frozen=True)
class AuditEvent:
    """What happened, before the decision: event kind, tool and the model-supplied order id."""

    event: str
    tool: str
    raw_order_id: object = None


@dataclass(frozen=True)
class AuditRecord:
    """One audit line. Every field is a short code or id; there is no free text."""

    event: str
    caller: str | None
    role: str | None
    store_id: str | None
    tool: str
    outcome: str
    reason: str
    order_ref: str | None


def order_reference(raw_order_id: object, salt: bytes) -> str | None:
    """Keyed, non-reversible reference to whatever order id the model supplied (or None).

    HMAC-SHA256 with a secret salt: the id space is only a million values, so an unkeyed hash
    could be reversed by enumeration.
    """
    if raw_order_id is None:
        return None
    # backslashreplace: a lone surrogate in a model-supplied id must never raise here.
    data = str(raw_order_id).encode("utf-8", errors="backslashreplace")
    digest = hmac.new(salt, data, hashlib.sha256).hexdigest()
    return digest[:_REF_LENGTH]


def build_audit_record(
    principal: Principal | None, event: AuditEvent, decision: Decision, salt: bytes
) -> AuditRecord:
    """Pure builder: the only place that decides which fields an audit record carries."""
    return AuditRecord(
        event=event.event,
        caller=principal.user_id if principal else None,
        role=principal.role if principal else None,
        store_id=principal.store_id if principal else None,
        tool=event.tool,
        outcome=OUTCOME_ALLOWED if decision.allowed else OUTCOME_DENIED,
        reason=decision.reason,
        order_ref=order_reference(event.raw_order_id, salt),
    )


class AuditLogger:
    """Writes audit records through one named logger.

    `salt` defaults to a random per-process secret, so references correlate within a run but
    cannot be rebuilt from an order id afterwards.
    """

    def __init__(self, salt: bytes | None = None) -> None:
        self._salt = salt if salt is not None else secrets.token_bytes(32)
        self._logger = logging.getLogger(AUDIT_LOGGER_NAME)

    def record(self, principal: Principal | None, event: AuditEvent, decision: Decision) -> None:
        """Build and emit one audit record."""
        record = build_audit_record(principal, event, decision, self._salt)
        self._logger.info("audit %s", json.dumps(asdict(record), sort_keys=True))
