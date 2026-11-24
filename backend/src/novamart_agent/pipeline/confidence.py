"""Confidence composite, band, loop exit and best-attempt selection (task 6.3, D11, D12).

The only loop bound: ADK's `Workflow` has no iteration cap, so `decide_loop` is what stops the
cycle (AGENT-6). All decisions are plain functions of typed values and configuration; no model
sets a score, a band or an exit.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from novamart_agent.config import PipelineSettings
from novamart_agent.models import ConfidenceBand, RetrievedChunk
from novamart_agent.pipeline.rubric_check import Assessment

_BAND_RANK: dict[ConfidenceBand, int] = {
    ConfidenceBand.LOW: 0,
    ConfidenceBand.MEDIUM: 1,
    ConfidenceBand.HIGH: 2,
}


class LoopRoute(StrEnum):
    """The values the `loop_decide` function node can emit."""

    RETRY = "retry"
    DONE = "done"


@dataclass(frozen=True)
class PassEvidence:
    """Everything one retrieval-and-validation pass produced.

    `score_floor` is the retrieval similarity threshold: the top cosine score is normalised
    from [floor, 1] to [0, 1] so a score at the gate counts as 0.
    """

    pass_number: int
    chunks: tuple[RetrievedChunk, ...]
    assessment: Assessment
    llm_confidence: float
    score_floor: float
    rewrite: str | None = None


@dataclass(frozen=True)
class Attempt:
    """A scored pass. The composer is given the best attempt, not necessarily the last."""

    pass_number: int
    composite: float
    band: ConfidenceBand
    required_uncovered: bool
    chunks: tuple[RetrievedChunk, ...]
    rewrite: str | None


@dataclass(frozen=True)
class LoopDecision:
    """`route` for the cycle's routed edge and the attempt to compose from."""

    route: LoopRoute
    best: Attempt


def normalised_score(chunks: Sequence[RetrievedChunk], floor: float) -> float:
    """Top cosine score rescaled from [floor, 1] to [0, 1]; 0 with no chunks."""
    if not chunks or floor >= 1.0:
        return 0.0
    top = max(c.score for c in chunks)
    return min(1.0, max(0.0, (top - floor) / (1.0 - floor)))


def composite_score(evidence: PassEvidence, settings: PipelineSettings) -> float:
    """Weighted sum of rubric coverage, normalised top score and the validator's confidence."""
    w = settings.weights
    total = (
        w.coverage * evidence.assessment.coverage
        + w.score * normalised_score(evidence.chunks, evidence.score_floor)
        + w.llm * min(1.0, max(0.0, evidence.llm_confidence))
    )
    return min(1.0, max(0.0, total))


def band_for(
    composite: float, required_uncovered: bool, settings: PipelineSettings
) -> ConfidenceBand:
    """High, Medium or Low from the thresholds. An uncovered required criterion caps at Low,
    whatever the sum (D12)."""
    if required_uncovered or composite < settings.bands.medium:
        return ConfidenceBand.LOW
    return ConfidenceBand.HIGH if composite >= settings.bands.high else ConfidenceBand.MEDIUM


def make_attempt(evidence: PassEvidence, settings: PipelineSettings) -> Attempt:
    """Score one pass."""
    composite = composite_score(evidence, settings)
    required_uncovered = evidence.assessment.required_uncovered
    return Attempt(
        evidence.pass_number,
        composite,
        band_for(composite, required_uncovered, settings),
        required_uncovered,
        evidence.chunks,
        evidence.rewrite,
    )


def _rank(attempt: Attempt) -> tuple[int, float]:
    return (_BAND_RANK[attempt.band], attempt.composite)


def best_attempt(attempts: Sequence[Attempt]) -> Attempt:
    """The best band, then the best composite. A later attempt replaces the current best only
    when strictly better, so a worse or equal second pass never replaces the first."""
    best = attempts[0]
    for candidate in attempts[1:]:
        if _rank(candidate) > _rank(best):
            best = candidate
    return best


def decide_loop(attempts: Sequence[Attempt], settings: PipelineSettings) -> LoopDecision:
    """Exit when the latest composite reaches T or `max_iterations` passes have run; else retry.

    `attempts` is every pass so far, oldest first, and must not be empty.
    """
    latest = attempts[-1]
    exhausted = len(attempts) >= settings.max_iterations
    reached = latest.composite >= settings.loop_exit_threshold
    route = LoopRoute.DONE if reached or exhausted else LoopRoute.RETRY
    return LoopDecision(route, best_attempt(attempts))
