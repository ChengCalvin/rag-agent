"""Types shared by the three tool files (private to `tools/`, ARCH-MOD-2).

No ADK imports: ADK injects `tool_context` by name and only its `state` is used, so a
`Protocol` describes it.
"""

from typing import Protocol

from novamart_agent.security import SessionState

Result = dict[str, object]


class ToolContextLike(Protocol):
    """The part of ADK's `ToolContext` the tools use."""

    @property
    def state(self) -> SessionState: ...
