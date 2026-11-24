"""The last node of every route: assemble and emit the reply (tasks 7.2, 7.6, D15, D17).

It counts the turn's cost (the composer's own usage is already in state), updates the session
total, builds the reply with `agents.reply` and emits it as `Event(content=...)`: that form is
what `adk run` and `adk web` show as the answer (probe `workflow-final-reply`).
"""

from google.adk import Context, Event
from google.genai import types

from novamart_agent.agents._io import NodeFunction, message_text
from novamart_agent.agents.deps import PipelineDeps
from novamart_agent.agents.reply import ReplyEnv, ReplyFacts, build_reply
from novamart_agent.pipeline import (
    STATE_ATTEMPTS,
    STATE_FINAL_KIND,
    STATE_ORDER_RESULTS,
    STATE_RETRIEVAL,
    STATE_RUBRIC,
    STATE_SESSION_COST,
    STATE_USAGE,
    ReplyKind,
    account_turn,
    attempts_from_state,
    best_attempt,
    parse_retrieval_result,
    rubric_from_state,
    session_cost_from_state,
    session_cost_to_state,
)
from novamart_agent.rag import build_catalog, escalation_contact


def _kind(raw: object) -> ReplyKind:
    """The kind the turn ended with; an unset or unknown value is the generic failure."""
    kinds = {k.value: k for k in ReplyKind}
    return kinds.get(raw, ReplyKind.FAILURE) if isinstance(raw, str) else ReplyKind.FAILURE


def _closest_titles(raw: object) -> tuple[str, ...]:
    return parse_retrieval_result(raw).closest_titles if isinstance(raw, dict) else ()


def _facts(ctx: Context, node_input: object) -> ReplyFacts:
    state = ctx.state
    rubric_raw = state.get(STATE_RUBRIC)
    attempts = attempts_from_state(state.get(STATE_ATTEMPTS))
    orders = state.get(STATE_ORDER_RESULTS)
    return ReplyFacts(
        kind=_kind(state.get(STATE_FINAL_KIND)),
        composed=message_text(node_input),
        rubric=rubric_from_state(rubric_raw) if rubric_raw is not None else None,
        best=best_attempt(attempts) if attempts else None,
        order_results=orders if isinstance(orders, dict) else {},
        closest_titles=_closest_titles(state.get(STATE_RETRIEVAL)),
    )


def make_finish_reply(deps: PipelineDeps) -> NodeFunction:
    """Build the finishing node. The catalog and the escalation contact are read from the
    loaded documents once, here, so a missing contact fails at startup (D13)."""
    settings = deps.settings
    env = ReplyEnv(
        build_catalog(deps.documents), settings.docs_path_label, escalation_contact(deps.documents)
    )

    def finish_reply(ctx: Context, node_input: object) -> Event:
        account = account_turn(
            ctx.state.get(STATE_USAGE),
            session_cost_from_state(ctx.state.get(STATE_SESSION_COST)),
            settings.prices,
            settings.show_cost,
        )
        ctx.state[STATE_SESSION_COST] = session_cost_to_state(account.session)
        text = build_reply(_facts(ctx, node_input), env, account.line)
        return Event(content=types.Content(role="model", parts=[types.Part(text=text)]))

    return finish_reply
