"""Routing decisions after a tool or a validator pass (tasks 7.2 to 7.4, D11, D13, ERR-4).

Pure: each function maps typed values to a route and, for a route that ends the turn, the kind
of the final reply. The function nodes only read state, call these and emit the result.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from novamart_agent.config import PipelineSettings
from novamart_agent.models import (
    TOOL_STATUS_NO_ANSWER,
    TOOL_STATUS_NOT_DETERMINABLE,
    TOOL_STATUS_NOT_FOUND,
    TOOL_STATUS_OK,
    Rubric,
    Verdict,
)
from novamart_agent.pipeline.confidence import (
    Attempt,
    LoopRoute,
    PassEvidence,
    decide_loop,
    make_attempt,
)
from novamart_agent.pipeline.retrieval_result import RetrievalResult
from novamart_agent.pipeline.routes import AfterOrderRoute, AfterRetrievalRoute, ReplyKind
from novamart_agent.pipeline.routing import TurnRoute
from novamart_agent.pipeline.rubric_check import assess


@dataclass(frozen=True)
class RetrievalStep:
    """Where the turn goes after a `search_policy` result. `kind` is set only on a refusal."""

    route: AfterRetrievalRoute
    kind: ReplyKind | None


@dataclass(frozen=True)
class OrderStep:
    """Where the turn goes after the order agent. `kind` is the final reply kind."""

    route: AfterOrderRoute
    kind: ReplyKind


@dataclass(frozen=True)
class LoopInputs:
    """What one validator pass produced: the rubric, the verdict, the retrieval result and the
    retrieval similarity threshold (the floor of the normalised score)."""

    rubric: Rubric
    verdict: Verdict
    retrieval: RetrievalResult
    score_floor: float


@dataclass(frozen=True)
class LoopStep:
    """The attempts so far (this pass last), the route, and the attempt to compose from."""

    attempts: tuple[Attempt, ...]
    route: LoopRoute
    best: Attempt


def retrieval_step(result: RetrievalResult | None, has_attempts: bool) -> RetrievalStep:
    """`ok` goes to the validator. `no_answer` is case C, and so is a denied search (it must look
    like finding nothing). Anything else, or no result at all, is the generic failure.

    A non-`ok` result on a retry pass (`has_attempts`) does not discard the evidence an earlier
    pass found: the turn composes from the best attempt, so a worse second pass never replaces a
    better first one (D11).
    """
    if result is not None and result.status == TOOL_STATUS_OK:
        return RetrievalStep(AfterRetrievalRoute.VALIDATE, None)
    if has_attempts:
        return RetrievalStep(AfterRetrievalRoute.COMPOSE, None)
    if result is not None and result.status in (TOOL_STATUS_NO_ANSWER, TOOL_STATUS_NOT_FOUND):
        return RetrievalStep(AfterRetrievalRoute.REFUSE, ReplyKind.NO_EVIDENCE)
    return RetrievalStep(AfterRetrievalRoute.REFUSE, ReplyKind.FAILURE)


def _status(result: Mapping[str, object]) -> object:
    return result.get("status")


def order_step(results: Mapping[str, Mapping[str, object]]) -> OrderStep:
    """Map the order tool results of one turn to a route (D13 cases D and F).

    A denial wins over everything else, so the reply is the same whatever else was returned.
    No tool result at all (the agent did not call a tool) is also the uniform not-found.
    """
    statuses = [_status(r) for r in results.values()]
    if not statuses or TOOL_STATUS_NOT_FOUND in statuses:
        return OrderStep(AfterOrderRoute.FINAL, ReplyKind.NOT_FOUND)
    if TOOL_STATUS_NOT_DETERMINABLE in statuses:
        return OrderStep(AfterOrderRoute.FINAL, ReplyKind.NOT_DETERMINABLE)
    if any(s != TOOL_STATUS_OK for s in statuses):
        return OrderStep(AfterOrderRoute.FINAL, ReplyKind.FAILURE)
    return OrderStep(AfterOrderRoute.COMPOSE, ReplyKind.ORDER_ANSWER)


def loop_step(
    previous: Sequence[Attempt], inputs: LoopInputs, settings: PipelineSettings
) -> LoopStep:
    """Score this pass and decide to retry or finish (D11, D12).

    The exit is `decide_loop` (threshold or `max_iterations`). A retry needs a rewritten query to
    try: with none, a second search would repeat the first, so the loop ends.
    """
    evidence = PassEvidence(
        pass_number=len(previous) + 1,
        chunks=inputs.retrieval.chunks,
        assessment=assess(inputs.rubric, inputs.verdict, inputs.retrieval.status),
        llm_confidence=inputs.verdict.llm_confidence,
        score_floor=inputs.score_floor,
        rewrite=inputs.verdict.rewritten_query,
    )
    attempts = (*previous, make_attempt(evidence, settings))
    decision = decide_loop(attempts, settings)
    retry_possible = decision.route is LoopRoute.RETRY and evidence.rewrite is not None
    route = LoopRoute.RETRY if retry_possible else LoopRoute.DONE
    return LoopStep(attempts, route, decision.best)


def ending_kind(route: TurnRoute) -> ReplyKind | None:
    """The reply kind of a route that ends the turn at once (clarify, decline), else None."""
    if route is TurnRoute.CLARIFY:
        return ReplyKind.CLARIFY
    if route is TurnRoute.DECLINE:
        return ReplyKind.DECLINE
    return None
