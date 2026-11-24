"""ADK callbacks for identity and the before-tool allowlist and audit (LAYER-1; tasks 3.1, 3.3).

Only adapts ADK to the pure functions in `principal`, `guard` and `audit`; decisions live there.
Wiring them onto agents is chunk 7.
"""

from collections.abc import Callable

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from novamart_agent.config import Settings
from novamart_agent.models import ORDER_TOOLS, STATE_PRINCIPAL
from novamart_agent.security.audit import EVENT_TOOL_CALL, AuditEvent, AuditLogger
from novamart_agent.security.guard import authorize_tool, denied_result
from novamart_agent.security.principal import (
    load_principals,
    principal_from_state,
    principal_to_state,
    resolve_principal,
)

# The order tools' parameter holding the order id (tools are written in chunk 5 to match).
ORDER_ID_ARG = "order_id"

IdentityCallback = Callable[[CallbackContext], None]
BeforeToolCallback = Callable[[BaseTool, dict[str, object], ToolContext], dict[str, object] | None]


def make_identity_callback(settings: Settings) -> IdentityCallback:
    """Before-agent callback: write the `NOVAMART_USER` persona into session state.

    Runs every turn and overwrites the key, so nothing a user or model wrote there survives.
    An unset or unknown persona clears it (None), which every consumer denies.
    Personas are loaded once here; a broken `users.json` fails at startup, not mid-chat.
    """
    principals = load_principals(settings.data_dir / "users.json")
    principal = resolve_principal(settings.user, principals)

    def set_identity(callback_context: CallbackContext) -> None:
        callback_context.state[STATE_PRINCIPAL] = principal_to_state(principal)

    return set_identity


def make_before_tool_callback(audit: AuditLogger) -> BeforeToolCallback:
    """Before-tool callback: per-role allowlist, then one audit record for the call.

    A disallowed call returns the uniform denial dict, which ADK uses as the tool result, and
    the tool never runs. The true order outcome is audited by the guard inside the tool.
    """

    def check_tool(
        tool: BaseTool, args: dict[str, object], tool_context: ToolContext
    ) -> dict[str, object] | None:
        principal = principal_from_state(tool_context.state)
        decision = authorize_tool(principal, tool.name)
        raw_id = args.get(ORDER_ID_ARG) if tool.name in ORDER_TOOLS else None
        audit.record(principal, AuditEvent(EVENT_TOOL_CALL, tool.name, raw_id), decision)
        return None if decision.allowed else dict(denied_result())

    return check_tool
