"""JSON-safe forms of typed pipeline values kept in session state (tasks 7.2, 7.3, 7.6).

Session state holds plain JSON values, so rubrics, attempts and the session cost are converted
here, both ways. Reading is strict: a value that does not have the shape written here is a code
bug and raises `StateDataError` (a key name, never a value). Nothing here reads a model reply.
"""

from collections.abc import Mapping, Sequence

from novamart_agent.errors import StateDataError
from novamart_agent.models import (
    ConfidenceBand,
    Criterion,
    RetrievedChunk,
    Route,
    Rubric,
)
from novamart_agent.pipeline.confidence import Attempt
from novamart_agent.pipeline.cost import SessionCost


def _fail(what: str) -> StateDataError:
    return StateDataError(f"state value '{what}' is malformed")


def _mapping(raw: object, what: str) -> Mapping[str, object]:
    if not isinstance(raw, dict):
        raise _fail(what)
    return raw


def _list(raw: object, what: str) -> list[object]:
    if not isinstance(raw, list):
        raise _fail(what)
    return raw


def _str(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise _fail(key)
    return value


def _bool(entry: Mapping[str, object], key: str) -> bool:
    value = entry.get(key)
    if not isinstance(value, bool):
        raise _fail(key)
    return value


def _number(entry: Mapping[str, object], key: str) -> float:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _fail(key)
    return float(value)


def _int(entry: Mapping[str, object], key: str) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(key)
    return value


def _opt_str(entry: Mapping[str, object], key: str) -> str | None:
    value = entry.get(key)
    if value is not None and not isinstance(value, str):
        raise _fail(key)
    return value


def rubric_to_state(rubric: Rubric) -> dict[str, object]:
    """The JSON-safe form of a rubric."""
    return {
        "route": rubric.route.value,
        "doc_type": rubric.doc_type,
        "criteria": [
            {"text": c.text, "required": c.required, "unanswered_policy": c.unanswered_policy}
            for c in rubric.criteria
        ],
        "missing_slots": list(rubric.missing_slots),
    }


def rubric_from_state(raw: object) -> Rubric:
    """Read back a rubric written by `rubric_to_state`."""
    data = _mapping(raw, "rubric")
    criteria = tuple(
        Criterion(_str(c, "text"), _bool(c, "required"), _bool(c, "unanswered_policy"))
        for c in (_mapping(i, "criteria") for i in _list(data.get("criteria"), "criteria"))
    )
    slots = _list(data.get("missing_slots"), "missing_slots")
    if not all(isinstance(s, str) for s in slots):
        raise _fail("missing_slots")
    return Rubric(
        Route(_str(data, "route")),
        _opt_str(data, "doc_type"),
        criteria,
        tuple(str(s) for s in slots),
    )


def _chunk_to_state(chunk: RetrievedChunk) -> dict[str, object]:
    return {
        "document_id": chunk.document_id,
        "heading": chunk.heading,
        "file_name": chunk.file_name,
        "doc_type": chunk.doc_type,
        "text": chunk.text,
        "score": chunk.score,
    }


def _chunk_from_state(raw: object) -> RetrievedChunk:
    data = _mapping(raw, "chunk")
    return RetrievedChunk(
        _str(data, "document_id"),
        _str(data, "heading"),
        _str(data, "file_name"),
        _str(data, "doc_type"),
        _str(data, "text"),
        _number(data, "score"),
    )


def attempt_to_state(attempt: Attempt) -> dict[str, object]:
    """The JSON-safe form of one scored pass."""
    return {
        "pass_number": attempt.pass_number,
        "composite": attempt.composite,
        "band": attempt.band.value,
        "required_uncovered": attempt.required_uncovered,
        "chunks": [_chunk_to_state(c) for c in attempt.chunks],
        "rewrite": attempt.rewrite,
        "inputs": list(attempt.inputs),
    }


def attempt_from_state(raw: object) -> Attempt:
    """Read back an attempt written by `attempt_to_state`."""
    data = _mapping(raw, "attempt")
    return Attempt(
        _int(data, "pass_number"),
        _number(data, "composite"),
        ConfidenceBand(_str(data, "band")),
        _bool(data, "required_uncovered"),
        tuple(_chunk_from_state(c) for c in _list(data.get("chunks"), "chunks")),
        _opt_str(data, "rewrite"),
        _inputs(data.get("inputs")),
    )


def _inputs(raw: object) -> tuple[float, float, float]:
    """The composite's three inputs; an older record without them reads as zeros."""
    if not isinstance(raw, list) or len(raw) != 3:
        return (0.0, 0.0, 0.0)
    a, b, c = (float(v) for v in raw)
    return (a, b, c)


def attempts_to_state(attempts: Sequence[Attempt]) -> list[dict[str, object]]:
    """The attempts of this turn, oldest first."""
    return [attempt_to_state(a) for a in attempts]


def attempts_from_state(raw: object) -> tuple[Attempt, ...]:
    """The attempts of this turn; absent or None means none yet."""
    if raw is None:
        return ()
    return tuple(attempt_from_state(a) for a in _list(raw, "attempts"))


def session_cost_to_state(session: SessionCost) -> dict[str, object]:
    """The JSON-safe form of the running session total."""
    return {
        "usd": session.usd,
        "questions": session.questions,
        "unpriced_questions": session.unpriced_questions,
    }


def session_cost_from_state(raw: object) -> SessionCost:
    """The running session total; absent or None is a new session (zero)."""
    if raw is None:
        return SessionCost()
    data = _mapping(raw, "session_cost")
    return SessionCost(
        _number(data, "usd"), _int(data, "questions"), _int(data, "unpriced_questions")
    )
