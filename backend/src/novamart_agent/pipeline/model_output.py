"""Parse model-produced intermediates into typed values, once (ARCH-BOUND-1 b, AGENT-4).

The rubric and the verdict are untrusted data. These parsers accept anything, never raise, and
fall back to the safe reading: a malformed or empty rubric becomes one required criterion made
from the user message, and a malformed verdict says nothing is covered with zero confidence
(it can only lower confidence, never lift a refusal; ERR-4). Free text is cleaned and capped.
"""

import json
import math
import unicodedata
from collections.abc import Mapping

from novamart_agent.config import PipelineSettings
from novamart_agent.models import DOC_TYPES, Criterion, Route, Rubric, Verdict

MAX_SLOTS = 5
MAX_SLOT_CHARS = 40
_KEY_ROUTE = "route"
_KEY_DOC_TYPE = "doc_type"
_KEY_CRITERIA = "criteria"
_KEY_SLOTS = "missing_slots"
_KEY_COVERAGE = "coverage"
_KEY_CONFIDENCE = "llm_confidence"
_KEY_REWRITE = "rewritten_query"


def clean_text(raw: str, max_chars: int) -> str:
    """Control characters dropped, whitespace collapsed to single spaces, cut to `max_chars`."""
    kept = "".join(
        " " if c.isspace() else c for c in raw if c.isspace() or unicodedata.category(c) != "Cc"
    )
    return " ".join(kept.split())[:max_chars].strip()


def _as_mapping(raw: object) -> Mapping[str, object] | None:
    """The mapping a model returned, directly or as a JSON string; None for anything else."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if isinstance(raw, dict) and all(isinstance(k, str) for k in raw):
        return raw
    return None


def fallback_rubric(user_message: str, settings: PipelineSettings, route: Route) -> Rubric:
    """One required criterion made from the user message (design Risks: rubric quality)."""
    text = clean_text(user_message, settings.criterion_max_chars)
    return Rubric(route, None, (Criterion(text or "answer the question", True),))


def _parse_criterion(item: object, settings: PipelineSettings) -> Criterion | None:
    if not isinstance(item, dict):
        return None
    text = item.get("text")
    if not isinstance(text, str) or not (cleaned := clean_text(text, settings.criterion_max_chars)):
        return None
    required = item.get("required")
    unanswered = item.get("unanswered_policy")
    return Criterion(
        cleaned,
        required if isinstance(required, bool) else True,  # unclear means required (stricter)
        unanswered if isinstance(unanswered, bool) else False,
    )


def _parse_criteria(raw: object, settings: PipelineSettings) -> tuple[Criterion, ...]:
    if not isinstance(raw, list) or len(raw) > settings.rubric_max_criteria:
        return ()
    parsed = (_parse_criterion(item, settings) for item in raw)
    return tuple(c for c in parsed if c is not None)


def _parse_slots(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    slots = (clean_text(s, MAX_SLOT_CHARS) for s in raw if isinstance(s, str))
    return tuple(s for s in slots if s)[:MAX_SLOTS]


def parse_rubric(raw: object, user_message: str, settings: PipelineSettings) -> Rubric:
    """Turn intake output into a `Rubric`. An unreadable route falls back to `knowledge`, where
    the deterministic retrieval gate still refuses what the documents do not support."""
    data = _as_mapping(raw)
    route_value = data.get(_KEY_ROUTE) if data else None
    routes = {r.value: r for r in Route}
    route = routes.get(route_value) if isinstance(route_value, str) else None
    if data is None or route is None:
        return fallback_rubric(user_message, settings, Route.KNOWLEDGE)
    criteria = _parse_criteria(data.get(_KEY_CRITERIA), settings)
    if not criteria:
        return fallback_rubric(user_message, settings, route)
    doc_type = data.get(_KEY_DOC_TYPE)
    return Rubric(
        route,
        doc_type if isinstance(doc_type, str) and doc_type in DOC_TYPES else None,
        criteria,
        _parse_slots(data.get(_KEY_SLOTS)),
    )


def _covered_flags(raw: object, count: int) -> tuple[bool, ...]:
    """One strict boolean per criterion; anything missing or not a real `True` is uncovered."""
    entries = raw if isinstance(raw, list) else []
    flags: list[bool] = []
    for index in range(count):
        entry = entries[index] if index < len(entries) else None
        value = entry.get("covered") if isinstance(entry, dict) else entry
        flags.append(value is True)
    return tuple(flags)


def _unit_number(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or math.isnan(raw):
        return 0.0
    return min(1.0, max(0.0, float(raw)))


def parse_verdict(raw: object, criteria_count: int, settings: PipelineSettings) -> Verdict:
    """Turn validator output into a `Verdict` with one flag per rubric criterion."""
    data = _as_mapping(raw)
    if data is None:
        return Verdict((False,) * criteria_count, 0.0, None)
    rewrite = data.get(_KEY_REWRITE)
    cleaned = clean_text(rewrite, settings.rewrite_max_chars) if isinstance(rewrite, str) else ""
    return Verdict(
        _covered_flags(data.get(_KEY_COVERAGE), criteria_count),
        _unit_number(data.get(_KEY_CONFIDENCE)),
        cleaned or None,
    )
