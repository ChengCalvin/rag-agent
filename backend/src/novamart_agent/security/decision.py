"""Authorization decision type and reason codes (LAYER-3, no ADK imports).

Reasons are a closed set of short codes. They go to the audit record only; the model-facing
response is identical for every denial (ARCH-ERR-1).
"""

from dataclasses import dataclass

REASON_ALLOWED = "allowed"
REASON_NO_PRINCIPAL = "no_principal"
REASON_UNKNOWN_ROLE = "unknown_role"
REASON_NO_SCOPE = "no_scope"  # store-less employee or manager, region-less regional manager
REASON_OUT_OF_SCOPE = "out_of_scope"
REASON_MALFORMED_ID = "malformed_id"
REASON_NOT_FOUND = "not_found"
REASON_THROTTLED = "throttled"
REASON_TOOL_NOT_ALLOWED = "tool_not_allowed"


@dataclass(frozen=True)
class Decision:
    """Allow or deny, with the true reason for the audit trail."""

    allowed: bool
    reason: str


ALLOW = Decision(True, REASON_ALLOWED)


def deny(reason: str) -> Decision:
    """A denial with its audit reason."""
    return Decision(False, reason)
