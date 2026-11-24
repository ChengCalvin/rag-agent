"""Principal, authorization guard and audit (LAYER-3); ADK callbacks live in `callbacks.py`.

Public names are exposed here (ARCH-MOD-2); other packages import only these. `callbacks.py` is
LAYER-1 (ADK wiring) and is deliberately not re-exported: importing it pulls in ADK, which the
tools and pure layers must not do. Agent wiring imports `novamart_agent.security.callbacks`.
"""

from novamart_agent.security.audit import (
    AuditEvent,
    AuditLogger,
    AuditRecord,
    build_audit_record,
    order_reference,
)
from novamart_agent.security.decision import Decision
from novamart_agent.security.guard import (
    OrderAccess,
    OrderGuard,
    OrderRequest,
    authorize_order,
    authorize_tool,
    denied_result,
    is_throttled,
    parse_order_id,
    permitted_audiences,
)
from novamart_agent.security.principal import (
    SessionState,
    load_principals,
    principal_from_state,
    principal_to_state,
    resolve_principal,
)

__all__: list[str] = [
    "AuditEvent",
    "AuditLogger",
    "AuditRecord",
    "Decision",
    "OrderAccess",
    "OrderGuard",
    "OrderRequest",
    "SessionState",
    "authorize_order",
    "authorize_tool",
    "build_audit_record",
    "denied_result",
    "is_throttled",
    "load_principals",
    "order_reference",
    "parse_order_id",
    "permitted_audiences",
    "principal_from_state",
    "principal_to_state",
    "resolve_principal",
]
