"""Overall results: pass rates, call counts and cost per question (pure)."""

from collections.abc import Sequence
from dataclasses import dataclass

from evalkit.grade import CaseResult, TurnMetrics

COST_AT_QUESTIONS = 1000


@dataclass(frozen=True)
class GroupStats:
    """Pass rate and mean cost of a group of cases (one question type)."""

    name: str
    cases: int
    passed: int
    questions: int
    mean_calls: float
    mean_usd: float | None


@dataclass(frozen=True)
class Summary:
    """The overall figures of a run."""

    name: str
    total: int
    passed: int
    pass_rate: float
    groups: tuple[GroupStats, ...]
    failures: tuple[CaseResult, ...]
    mean_calls: float
    mean_usd: float | None
    usd_at_1000: float | None


def _turns(results: Sequence[CaseResult]) -> list[TurnMetrics]:
    return [t for r in results for t in r.turns]


def _mean_usd(turns: Sequence[TurnMetrics]) -> float | None:
    """Mean over questions; None when there are none or any has no price (never a $0)."""
    if not turns or any(t.usd is None for t in turns):
        return None
    return sum(t.usd or 0.0 for t in turns) / len(turns)


def _mean_calls(turns: Sequence[TurnMetrics]) -> float:
    return sum(t.model_calls for t in turns) / len(turns) if turns else 0.0


def _group(name: str, results: Sequence[CaseResult]) -> GroupStats:
    turns = _turns(results)
    passed = sum(1 for r in results if r.passed)
    return GroupStats(
        name, len(results), passed, len(turns), _mean_calls(turns), _mean_usd(turns)
    )


def pass_rate(results: Sequence[CaseResult]) -> float:
    """Fraction of cases that passed; 0.0 for no cases."""
    return sum(1 for r in results if r.passed) / len(results) if results else 0.0


def summarize(name: str, results: Sequence[CaseResult]) -> Summary:
    """Every failing case is kept, none omitted (spec: 'Results are reported honestly')."""
    types = sorted({r.question_type for r in results})
    turns = _turns(results)
    mean = _mean_usd(turns)
    return Summary(
        name=name,
        total=len(results),
        passed=sum(1 for r in results if r.passed),
        pass_rate=pass_rate(results),
        groups=tuple(_group(t, [r for r in results if r.question_type == t]) for t in types),
        failures=tuple(r for r in results if not r.passed),
        mean_calls=_mean_calls(turns),
        mean_usd=mean,
        usd_at_1000=None if mean is None else mean * COST_AT_QUESTIONS,
    )
