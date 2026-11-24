"""Function nodes of the knowledge and order routes (tasks 7.3, 7.4, D11, D14).

Thin adapters: read state, call one pure function from `pipeline/`, write state, emit a route.
The retrieval-validator cycle's exit and its bound are `pipeline.loop_step`, never a model.
"""

from google.adk import Context, Event

from novamart_agent.agents._io import NodeFunction, routed, user_message
from novamart_agent.agents.deps import PipelineDeps
from novamart_agent.errors import StateDataError
from novamart_agent.pipeline import (
    STATE_ATTEMPTS,
    STATE_FINAL_KIND,
    STATE_ORDER_RESULTS,
    STATE_QUERY_HINT,
    STATE_RETRIEVAL,
    STATE_ROUTE,
    STATE_RUBRIC,
    AfterOrderRoute,
    LoopInputs,
    LoopRoute,
    ReplyKind,
    RetrievalResult,
    TurnRoute,
    attempts_from_state,
    attempts_to_state,
    best_attempt,
    knowledge_composer_message,
    loop_step,
    order_composer_message,
    order_step,
    parse_retrieval_result,
    parse_verdict,
    retrieval_step,
    rubric_from_state,
    validator_message,
)


def _retrieval(raw: object) -> RetrievalResult | None:
    return parse_retrieval_result(raw) if isinstance(raw, dict) else None


def make_after_order() -> NodeFunction:
    """After the order agent: route on the stored tool results (D13 cases D and F)."""

    def after_order(ctx: Context, node_input: object) -> Event:
        raw = ctx.state.get(STATE_ORDER_RESULTS)
        step = order_step(raw if isinstance(raw, dict) else {})
        if step.route is AfterOrderRoute.FINAL:
            ctx.state[STATE_FINAL_KIND] = step.kind.value
        return routed(step.route.value)

    return after_order


def make_after_retrieval() -> NodeFunction:
    """After a retrieval pass: validate, refuse (case C) or fail, from the stored result."""

    def after_retrieval(ctx: Context, node_input: object) -> Event:
        result = _retrieval(ctx.state.get(STATE_RETRIEVAL))
        has_attempts = bool(ctx.state.get(STATE_ATTEMPTS))
        step = retrieval_step(result, has_attempts)
        if step.kind is not None:
            ctx.state[STATE_FINAL_KIND] = step.kind.value
        return routed(step.route.value, user_message(ctx.state))

    return after_retrieval


def make_prepare_validation() -> NodeFunction:
    """Build the validator's input: rubric and chunks as one data record (D16)."""

    def prepare_validation(ctx: Context, node_input: object) -> Event:
        rubric = rubric_from_state(ctx.state.get(STATE_RUBRIC))
        result = _retrieval(ctx.state.get(STATE_RETRIEVAL))
        chunks = result.chunks if result else ()
        return Event(output=validator_message(rubric, chunks))

    return prepare_validation


def make_loop_decide(deps: PipelineDeps) -> NodeFunction:
    """Score the pass and route `retry` or `done` from `pipeline.loop_step`; on a retry, store
    the rewrite for the query-hint callback and clear the old result."""
    settings = deps.settings

    def loop_decide(ctx: Context, node_input: object) -> Event:
        rubric = rubric_from_state(ctx.state.get(STATE_RUBRIC))
        retrieval = _retrieval(ctx.state.get(STATE_RETRIEVAL))
        if retrieval is None:
            raise StateDataError("state value 'retrieval_result' is missing")
        verdict = parse_verdict(node_input, len(rubric.criteria), settings.pipeline)
        inputs = LoopInputs(rubric, verdict, retrieval, settings.similarity_threshold)
        previous = attempts_from_state(ctx.state.get(STATE_ATTEMPTS))
        step = loop_step(previous, inputs, settings.pipeline)
        ctx.state[STATE_ATTEMPTS] = attempts_to_state(step.attempts)
        if step.route is LoopRoute.RETRY:
            ctx.state[STATE_QUERY_HINT] = step.attempts[-1].rewrite
            ctx.state[STATE_RETRIEVAL] = None
        return routed(step.route.value, user_message(ctx.state))

    return loop_decide


def make_prepare_compose() -> NodeFunction:
    """Build the composer's input: the best attempt (not the last) or the order records."""

    def prepare_compose(ctx: Context, node_input: object) -> Event:
        question = user_message(ctx.state)
        if ctx.state.get(STATE_ROUTE) == TurnRoute.ORDER.value:
            results = ctx.state.get(STATE_ORDER_RESULTS)
            ctx.state[STATE_FINAL_KIND] = ReplyKind.ORDER_ANSWER.value
            records = results if isinstance(results, dict) else {}
            return Event(output=order_composer_message(question, records))
        rubric = rubric_from_state(ctx.state.get(STATE_RUBRIC))
        best = best_attempt(attempts_from_state(ctx.state.get(STATE_ATTEMPTS)))
        ctx.state[STATE_FINAL_KIND] = ReplyKind.KNOWLEDGE_ANSWER.value
        return Event(output=knowledge_composer_message(question, rubric, best.chunks))

    return prepare_compose
