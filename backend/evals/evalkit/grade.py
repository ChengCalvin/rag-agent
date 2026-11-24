"""Grade one case: run its checks over what happened and keep the cost figures (pure)."""

import re
from dataclasses import dataclass

from evalkit.cases import Case
from evalkit.checks import run_check
from evalkit.observation import (
    Observation,
    SeededValue,
    TurnObservation,
    model_calls,
    outcome_of,
)
from evalkit.results import CheckResult


@dataclass(frozen=True)
class TurnMetrics:
    """Cost figures of one question, from the recorded usage (never from model text), plus the
    question and the reply as shown to the user, with seeded customer values redacted (ERR-2)."""

    model_calls: int
    usd: float | None
    input_tokens: int
    output_tokens: int
    outcome: str | None
    message: str = ""
    reply: str = ""


@dataclass(frozen=True)
class CaseResult:
    """The result of one case. `error` is set when the run itself failed (a failed case)."""

    case_id: str
    set_name: str
    scenario: str
    question_type: str
    known_limitation: bool
    passed: bool
    checks: tuple[CheckResult, ...]
    turns: tuple[TurnMetrics, ...]
    error: str | None = None


def redact(text: str, seeded: tuple[SeededValue, ...]) -> str:
    """`text` with each seeded customer value replaced by `[redacted:<label>]`, any letter case."""
    for value in sorted(seeded, key=lambda v: len(v.text), reverse=True):
        text = re.sub(re.escape(value.text), f"[redacted:{value.label}]", text, flags=re.IGNORECASE)
    return text


def turn_metrics(turn: TurnObservation, seeded: tuple[SeededValue, ...] = ()) -> TurnMetrics:
    cost = turn.cost
    return TurnMetrics(
        model_calls(turn),
        cost.usd,
        cost.input_tokens,
        cost.output_tokens,
        outcome_of(turn),
        redact(turn.message, seeded),
        redact(turn.reply, seeded),
    )


def grade_case(case: Case, obs: Observation) -> CaseResult:
    """Every check must pass. A check that cannot run (bad argument) fails the case, loudly."""
    results = tuple(run_check(c.kind, c.args, obs) for c in case.checks)
    return CaseResult(
        case.case_id,
        case.set_name,
        case.scenario,
        case.question_type,
        case.known_limitation,
        all(r.passed for r in results),
        results,
        tuple(turn_metrics(t, obs.seeded) for t in obs.turns),
    )


def failed_run(case: Case, error: str) -> CaseResult:
    """A case whose run raised (for example a model error): it fails and says why."""
    return CaseResult(
        case.case_id,
        case.set_name,
        case.scenario,
        case.question_type,
        case.known_limitation,
        False,
        (),
        (),
        error,
    )
