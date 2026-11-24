"""Rubric coverage check (task 6.3, D11, D12, ERR-4).

Coverage is the fraction of criteria the validator marked covered, computed here in code. The
downgrade-only rule: a retrieval result that is not `ok` (`no_answer`, `error`) is a
deterministic refusal or failure, so no verdict, however favourable, can make it answerable. A
verdict can only lower confidence or ask for a rewrite.
"""

from dataclasses import dataclass

from novamart_agent.models import TOOL_STATUS_OK, Rubric, Verdict


@dataclass(frozen=True)
class Assessment:
    """What the verdict says about the rubric, after the downgrade-only rule."""

    coverage: float
    required_uncovered: bool
    answerable: bool


def assess(rubric: Rubric, verdict: Verdict, retrieval_status: str) -> Assessment:
    """Compute coverage and the required-criterion flag for one retrieval pass.

    A criterion with no matching verdict entry counts as uncovered. A non-`ok` retrieval status
    zeroes coverage and marks every required criterion uncovered, whatever the verdict says.
    """
    total = len(rubric.criteria)
    if retrieval_status != TOOL_STATUS_OK or total == 0:
        return Assessment(0.0, any(c.required for c in rubric.criteria) or total == 0, False)
    flags = [i < len(verdict.covered) and verdict.covered[i] for i in range(total)]
    required_uncovered = any(c.required and not f for c, f in zip(rubric.criteria, flags))
    return Assessment(sum(flags) / total, required_uncovered, True)
