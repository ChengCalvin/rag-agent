"""Function nodes at the start of a turn: identity, precheck, route (tasks 7.2, 7.5).

Each node only reads state, calls one pure function, writes state and emits a route (STRUCT-3,
AGENT-2). The principal is written from the persona in configuration, never from a message.
"""

from google.adk import Context, Event

from novamart_agent.agents._io import NodeFunction, message_text, routed, user_message
from novamart_agent.agents.deps import PipelineDeps
from novamart_agent.pipeline import (
    STATE_CLARIFICATIONS,
    STATE_FINAL_KIND,
    STATE_ROUTE,
    STATE_RUBRIC,
    STATE_USER_MESSAGE,
    PrecheckRoute,
    ReplyKind,
    ending_kind,
    fresh_turn_state,
    parse_rubric,
    precheck,
    route_turn,
    rubric_to_state,
)
from novamart_agent.security.callbacks import make_identity_callback


def make_inject_identity(deps: PipelineDeps) -> NodeFunction:
    """First node: set the principal, clear last turn's keys, keep the user's message."""
    set_identity = make_identity_callback(deps.settings)

    def inject_identity(ctx: Context, node_input: object) -> Event:
        set_identity(ctx)
        for key, value in fresh_turn_state().items():
            ctx.state[key] = value
        message = message_text(node_input) or message_text(ctx.user_content)
        ctx.state[STATE_USER_MESSAGE] = message
        return Event(output=message)

    return inject_identity


def make_precheck(deps: PipelineDeps) -> NodeFunction:
    """Precheck the raw message before any model call (ARCH-BOUND-1 d)."""
    settings = deps.settings.pipeline

    def precheck_node(ctx: Context, node_input: object) -> Event:
        message = user_message(ctx.state)
        if precheck(message, settings).proceed:
            return routed(PrecheckRoute.PROCEED.value, message)
        ctx.state[STATE_FINAL_KIND] = ReplyKind.DECLINE.value
        return routed(PrecheckRoute.DECLINE.value)

    return precheck_node


def _count(raw: object) -> int:
    return raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else 0


def make_route_turn(deps: PipelineDeps) -> NodeFunction:
    """Parse the intake record once, route in code (D10, D13), count clarifications."""
    settings = deps.settings.pipeline

    def route_node(ctx: Context, node_input: object) -> Event:
        message = user_message(ctx.state)
        rubric = parse_rubric(node_input, message, settings)
        asked = _count(ctx.state.get(STATE_CLARIFICATIONS))
        decision = route_turn(rubric, asked, settings.clarification_cap)
        ctx.state[STATE_RUBRIC] = rubric_to_state(rubric)
        ctx.state[STATE_ROUTE] = decision.route.value
        ctx.state[STATE_CLARIFICATIONS] = decision.clarifications_asked
        kind = ending_kind(decision.route)
        if kind is not None:
            ctx.state[STATE_FINAL_KIND] = kind.value
        return routed(decision.route.value, message)

    return route_node
