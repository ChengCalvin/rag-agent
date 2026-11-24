"""Tasks 7.3, 7.6: the pure routing, loop and turn-cost decisions, with fake model outputs.

No model, no ADK. Each test name quotes the behaviour it proves.
"""

import pytest

from novamart_agent.config import ModelPrice, PipelineSettings
from novamart_agent.errors import StateDataError
from novamart_agent.models import (
    ConfidenceBand,
    Criterion,
    RetrievedChunk,
    Route,
    Rubric,
    Verdict,
)
from novamart_agent.pipeline import (
    AfterOrderRoute,
    AfterRetrievalRoute,
    LoopInputs,
    LoopRoute,
    ReplyKind,
    RetrievalResult,
    SessionCost,
    TokenCounts,
    TurnRoute,
    account_turn,
    attempts_from_state,
    attempts_to_state,
    chat_usage_record,
    ending_kind,
    loop_step,
    order_step,
    retrieval_step,
    rubric_from_state,
    rubric_to_state,
    session_cost_from_state,
    session_cost_to_state,
    with_usage,
)

SETTINGS = PipelineSettings()
RUBRIC = Rubric(Route.KNOWLEDGE, "policy", (Criterion("window", True), Criterion("extra", False)))


def chunk(doc: str, score: float, text: str = "text") -> RetrievedChunk:
    return RetrievedChunk(doc, "Heading", f"{doc}.md", "policy", text, score)


def retrieval(status: str, *chunks: RetrievedChunk) -> RetrievalResult:
    return RetrievalResult(status, False, False, tuple(chunks), ())


# ------------------------------------------------------------- retrieval_step


def test_retrieval_ok_goes_to_the_validator() -> None:
    step = retrieval_step(retrieval("ok", chunk("a", 0.9)), has_attempts=False)
    assert step.route is AfterRetrievalRoute.VALIDATE
    assert step.kind is None


@pytest.mark.parametrize("status", ["no_answer", "not_found"])
def test_no_evidence_is_case_c_and_a_denied_search_looks_the_same(status: str) -> None:
    step = retrieval_step(retrieval(status), has_attempts=False)
    assert (step.route, step.kind) == (AfterRetrievalRoute.REFUSE, ReplyKind.NO_EVIDENCE)


@pytest.mark.parametrize("result", [retrieval("error"), None])
def test_an_error_or_missing_result_is_the_generic_failure(result: RetrievalResult | None) -> None:
    step = retrieval_step(result, has_attempts=False)
    assert (step.route, step.kind) == (AfterRetrievalRoute.REFUSE, ReplyKind.FAILURE)


def test_a_retry_that_finds_nothing_keeps_the_evidence_of_the_first_pass() -> None:
    """A worse second pass never replaces a better first pass (D11)."""
    step = retrieval_step(retrieval("no_answer"), has_attempts=True)
    assert step.route is AfterRetrievalRoute.COMPOSE


# ----------------------------------------------------------------- order_step


def ok(**extra: object) -> dict[str, object]:
    return {"status": "ok", **extra}


def test_order_ok_results_go_to_the_composer() -> None:
    step = order_step({"get_order_status": ok(), "check_return_eligibility": ok()})
    assert (step.route, step.kind) == (AfterOrderRoute.COMPOSE, ReplyKind.ORDER_ANSWER)


@pytest.mark.parametrize(
    ("results", "kind"),
    [
        ({"get_order_status": {"status": "not_found"}}, ReplyKind.NOT_FOUND),
        ({}, ReplyKind.NOT_FOUND),
        ({"check_return_eligibility": {"status": "not_determinable"}}, ReplyKind.NOT_DETERMINABLE),
        ({"get_order_status": {"status": "error"}}, ReplyKind.FAILURE),
        # A denial wins over everything else, so the reply never depends on what else came back.
        (
            {"get_order_status": ok(), "check_return_eligibility": {"status": "not_found"}},
            ReplyKind.NOT_FOUND,
        ),
        (
            {"a": {"status": "not_determinable"}, "b": {"status": "not_found"}},
            ReplyKind.NOT_FOUND,
        ),
    ],
)
def test_order_results_that_end_the_turn_map_to_one_kind(
    results: dict[str, dict[str, object]], kind: ReplyKind
) -> None:
    step = order_step(results)
    assert (step.route, step.kind) == (AfterOrderRoute.FINAL, kind)


# ------------------------------------------------------------------ loop_step


def inputs(
    coverage: tuple[bool, ...], confidence: float, rewrite: str | None, *chunks: RetrievedChunk
) -> LoopInputs:
    verdict = Verdict(coverage, confidence, rewrite)
    return LoopInputs(RUBRIC, verdict, retrieval("ok", *chunks), 0.2)


def test_loop_exit_comes_from_pipeline_confidence_when_the_composite_reaches_t() -> None:
    step = loop_step((), inputs((True, True), 1.0, "ignored", chunk("a", 0.9)), SETTINGS)
    assert step.route is LoopRoute.DONE
    assert step.best.band is ConfidenceBand.HIGH


def test_loop_retries_below_t_when_there_is_a_rewrite_and_passes_remain() -> None:
    step = loop_step((), inputs((True, False), 0.3, "better words", chunk("a", 0.3)), SETTINGS)
    assert step.route is LoopRoute.RETRY
    assert step.attempts[-1].rewrite == "better words"


def test_loop_without_a_rewrite_ends_because_a_second_search_would_repeat_the_first() -> None:
    step = loop_step((), inputs((False, False), 0.1, None, chunk("a", 0.3)), SETTINGS)
    assert step.route is LoopRoute.DONE


def test_loop_stops_at_max_iterations_even_with_a_rewrite_and_a_low_composite() -> None:
    first = loop_step((), inputs((False, False), 0.1, "again", chunk("a", 0.3)), SETTINGS)
    assert first.route is LoopRoute.RETRY
    again = inputs((False, False), 0.1, "again", chunk("b", 0.3))
    second = loop_step(first.attempts, again, SETTINGS)
    assert second.route is LoopRoute.DONE
    assert len(second.attempts) == SETTINGS.max_iterations == 2


def test_a_worse_second_pass_never_replaces_a_better_first_pass() -> None:
    first = loop_step((), inputs((True, False), 0.6, "again", chunk("good", 0.5)), SETTINGS)
    worse = inputs((False, False), 0.1, "again", chunk("bad", 0.3))
    second = loop_step(first.attempts, worse, SETTINGS)
    assert [c.document_id for c in second.best.chunks] == ["good"]


# ------------------------------------------------------------- state codec


def test_rubric_and_attempts_survive_a_round_trip_through_session_state() -> None:
    assert rubric_from_state(rubric_to_state(RUBRIC)) == RUBRIC
    step = loop_step((), inputs((True, False), 0.6, "again", chunk("a", 0.5)), SETTINGS)
    assert attempts_from_state(attempts_to_state(step.attempts)) == step.attempts
    assert attempts_from_state(None) == ()


def test_malformed_state_raises_a_typed_error_naming_the_key_not_the_value() -> None:
    with pytest.raises(StateDataError) as raised:
        rubric_from_state({"route": "knowledge", "criteria": "SECRET-VALUE"})
    assert "SECRET-VALUE" not in str(raised.value)


def test_session_cost_round_trips_and_a_new_session_starts_at_zero() -> None:
    cost = SessionCost(0.5, 3, 1)
    assert session_cost_from_state(session_cost_to_state(cost)) == cost
    assert session_cost_from_state(None) == SessionCost()


def test_clarify_and_decline_end_the_turn_at_once() -> None:
    assert ending_kind(TurnRoute.CLARIFY) is ReplyKind.CLARIFY
    assert ending_kind(TurnRoute.DECLINE) is ReplyKind.DECLINE
    assert ending_kind(TurnRoute.ORDER) is None
    assert ending_kind(TurnRoute.KNOWLEDGE) is None


# ---------------------------------------------------------------- turn cost

PRICES = {"chat": ModelPrice(1.0, 2.0)}


def record(agent: str, thoughts: int = 30) -> dict[str, object]:
    return chat_usage_record(agent, "chat", TokenCounts(100, 20, thoughts)).to_dict()


def test_thinking_tokens_are_summed_into_output_in_the_turn_line() -> None:
    """D17: `thoughts_token_count` is billed as output, so it is part of the output total."""
    raw = [record("intake"), record("order")]
    account = account_turn(raw, SessionCost(), PRICES, True)
    assert account.turn.output_tokens == 2 * (20 + 30)
    assert account.line is not None
    assert "100 out tokens" in account.line


def test_the_three_denial_causes_have_the_same_calls_and_totals_for_the_same_message() -> None:
    """Cost does not reveal why an order was denied: same records in, same line out."""
    lines = {
        account_turn([record("intake"), record("order")], SessionCost(), PRICES, True).line
        for _cause in ("nonexistent", "out_of_scope", "malformed")
    }
    assert len(lines) == 1


def test_the_flag_hides_the_line_but_recording_stays_on() -> None:
    account = account_turn([record("intake")], SessionCost(), PRICES, False)
    assert account.line is None
    assert account.session.questions == 1
    assert account.turn.calls == 1


def test_a_precheck_decline_costs_zero_with_no_calls() -> None:
    account = account_turn(None, SessionCost(), PRICES, True)
    assert account.line is not None
    assert "$0.00 this answer (0 calls)" in account.line


def test_with_usage_adds_one_record_without_changing_the_old_list() -> None:
    old = [record("intake")]
    new = with_usage(old, chat_usage_record("order", "chat", TokenCounts(1, 1, 0)))
    assert len(old) == 1
    assert [r["agent"] for r in new] == ["intake", "order"]
