"""Task 6.3: rubric coverage, composite, band, loop exit and best attempt (ARCH-TEST-1)."""

from dataclasses import replace

import pytest

from novamart_agent.config import BandThresholds, ConfidenceWeights, PipelineSettings
from novamart_agent.models import (
    TOOL_STATUS_ERROR,
    TOOL_STATUS_NO_ANSWER,
    TOOL_STATUS_OK,
    ConfidenceBand,
    Criterion,
    RetrievedChunk,
    Route,
    Rubric,
    Verdict,
)
from novamart_agent.pipeline import (
    Assessment,
    Attempt,
    LoopRoute,
    PassEvidence,
    assess,
    band_for,
    best_attempt,
    composite_score,
    decide_loop,
    make_attempt,
    normalised_score,
    parse_verdict,
)

# Fixed test settings so the expected numbers do not depend on the shipped defaults (AG-15).
SETTINGS = PipelineSettings(
    loop_exit_threshold=0.7,
    weights=ConfidenceWeights(0.5, 0.3, 0.2),
    bands=BandThresholds(medium=0.5, high=0.75),
    max_iterations=2,
)
FLOOR = 0.6


def chunk(score: float) -> RetrievedChunk:
    return RetrievedChunk("returns-policy", "Window", "returns-policy.md", "policy", "text", score)


def rubric(*required: bool) -> Rubric:
    return Rubric(
        Route.KNOWLEDGE, "policy", tuple(Criterion(f"c{i}", r) for i, r in enumerate(required))
    )


def verdict(*covered: bool, llm: float = 0.5) -> Verdict:
    return Verdict(tuple(covered), llm, None)


def evidence(
    *, coverage: float = 1.0, required_uncovered: bool = False, top: float = 1.0, llm: float = 1.0
) -> PassEvidence:
    return PassEvidence(
        1, (chunk(top),), Assessment(coverage, required_uncovered, True), llm, FLOOR
    )


# --- coverage --------------------------------------------------------------------------------


def test_coverage_is_the_fraction_of_criteria_marked_covered() -> None:
    result = assess(rubric(True, False, False, False), verdict(True, True, False, False), "ok")
    assert result.coverage == 0.5
    assert result.required_uncovered is False
    assert result.answerable is True


def test_an_uncovered_required_criterion_is_flagged() -> None:
    result = assess(rubric(True, False), verdict(False, True), TOOL_STATUS_OK)
    assert result.required_uncovered is True
    assert result.coverage == 0.5


def test_a_short_verdict_counts_missing_entries_as_uncovered() -> None:
    result = assess(rubric(False, False, False), verdict(True), TOOL_STATUS_OK)
    assert result.coverage == pytest.approx(1 / 3)


@pytest.mark.parametrize("status", [TOOL_STATUS_NO_ANSWER, TOOL_STATUS_ERROR])
def test_downgrade_only_a_verdict_can_never_lift_a_deterministic_no_answer(status: str) -> None:
    glowing = Verdict((True, True), 1.0, None)
    result = assess(rubric(True, True), glowing, status)
    assert result.answerable is False
    assert result.coverage == 0.0
    assert result.required_uncovered is True
    attempt = make_attempt(
        PassEvidence(1, (), result, glowing.llm_confidence, FLOOR), SETTINGS
    )
    assert attempt.band is ConfidenceBand.LOW
    assert attempt.composite == pytest.approx(SETTINGS.weights.llm)


def test_a_malformed_validator_verdict_can_only_lower_confidence() -> None:
    parsed = parse_verdict("garbage", 2, SETTINGS)
    assert parsed == Verdict((False, False), 0.0, None)
    assert assess(rubric(True, True), parsed, TOOL_STATUS_OK).coverage == 0.0


def test_verdict_values_are_clamped_and_strictly_typed() -> None:
    raw = {
        "coverage": [{"covered": "true"}, {"covered": True}, 1],
        "llm_confidence": 7,
        "rewritten_query": "  new\x00 query  " + "x" * 400,
    }
    parsed = parse_verdict(raw, 3, SETTINGS)
    assert parsed.covered == (False, True, False)
    assert parsed.llm_confidence == 1.0
    assert parsed.rewritten_query is not None
    assert len(parsed.rewritten_query) == SETTINGS.rewrite_max_chars
    assert parse_verdict({"llm_confidence": float("nan")}, 1, SETTINGS).llm_confidence == 0.0
    assert parse_verdict({"llm_confidence": True}, 1, SETTINGS).llm_confidence == 0.0
    assert parse_verdict({"rewritten_query": "   "}, 1, SETTINGS).rewritten_query is None


# --- composite and bands -----------------------------------------------------------------------


def test_normalised_score_rescales_from_the_gate_to_one() -> None:
    assert normalised_score((chunk(0.6),), FLOOR) == 0.0
    assert normalised_score((chunk(0.8), chunk(0.7)), FLOOR) == pytest.approx(0.5)
    assert normalised_score((chunk(1.0),), FLOOR) == 1.0
    assert normalised_score((), FLOOR) == 0.0


def test_composite_is_the_weighted_sum_of_the_three_inputs() -> None:
    value = composite_score(evidence(coverage=0.5, top=0.8, llm=0.5), SETTINGS)
    assert value == pytest.approx(0.5 * 0.5 + 0.3 * 0.5 + 0.2 * 0.5)


@pytest.mark.parametrize(
    ("composite", "band"),
    [
        (1.0, ConfidenceBand.HIGH),
        (0.75, ConfidenceBand.HIGH),
        (0.7499, ConfidenceBand.MEDIUM),
        (0.5, ConfidenceBand.MEDIUM),
        (0.4999, ConfidenceBand.LOW),
        (0.0, ConfidenceBand.LOW),
    ],
)
def test_band_thresholds_give_high_medium_and_low(composite: float, band: ConfidenceBand) -> None:
    assert band_for(composite, False, SETTINGS) is band


def test_required_criterion_cap_holds_the_band_at_low_whatever_the_sum() -> None:
    assert band_for(1.0, True, SETTINGS) is ConfidenceBand.LOW
    attempt = make_attempt(evidence(required_uncovered=True), SETTINGS)
    assert attempt.composite == pytest.approx(1.0)
    assert attempt.band is ConfidenceBand.LOW


# --- loop exit and best attempt --------------------------------------------------------------


def attempt(pass_number: int, composite: float, band: ConfidenceBand) -> Attempt:
    return Attempt(pass_number, composite, band, False, (chunk(0.9),), None)


def test_loop_exits_done_when_the_composite_reaches_the_threshold() -> None:
    decision = decide_loop([attempt(1, 0.7, ConfidenceBand.MEDIUM)], SETTINGS)
    assert decision.route is LoopRoute.DONE


def test_loop_retries_below_the_threshold_while_passes_remain() -> None:
    decision = decide_loop([attempt(1, 0.4, ConfidenceBand.LOW)], SETTINGS)
    assert decision.route is LoopRoute.RETRY


def test_iteration_exhaustion_exits_done_even_below_the_threshold() -> None:
    history = [attempt(1, 0.2, ConfidenceBand.LOW), attempt(2, 0.3, ConfidenceBand.LOW)]
    assert decide_loop(history, SETTINGS).route is LoopRoute.DONE


def test_the_loop_is_bounded_for_any_max_iterations() -> None:
    for limit in (1, 2, 3):
        settings = replace(SETTINGS, max_iterations=limit)
        history: list[Attempt] = []
        for pass_number in range(1, 10):
            history.append(attempt(pass_number, 0.1, ConfidenceBand.LOW))
            if decide_loop(history, settings).route is LoopRoute.DONE:
                break
        assert len(history) == limit


def test_a_worse_second_pass_never_replaces_a_better_first_pass() -> None:
    first = attempt(1, 0.65, ConfidenceBand.MEDIUM)
    second = attempt(2, 0.30, ConfidenceBand.LOW)
    decision = decide_loop([first, second], SETTINGS)
    assert decision.best is first
    assert best_attempt([first, second]) is first


def test_a_better_second_pass_replaces_the_first_and_a_tie_keeps_the_first() -> None:
    first = attempt(1, 0.40, ConfidenceBand.LOW)
    better = attempt(2, 0.80, ConfidenceBand.HIGH)
    assert best_attempt([first, better]) is better
    tie = attempt(2, 0.40, ConfidenceBand.LOW)
    assert best_attempt([first, tie]) is first


def test_a_higher_composite_under_the_required_cap_does_not_beat_a_better_band() -> None:
    capped = Attempt(2, 0.9, ConfidenceBand.LOW, True, (chunk(0.9),), None)
    first = attempt(1, 0.55, ConfidenceBand.MEDIUM)
    assert best_attempt([first, capped]) is first
