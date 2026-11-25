"""The final reply of every route, assembled in code (task 7.2, 7.4, D13, D15, AGENT-3).

The kind of reply was decided upstream by `pipeline`; this module maps it to canned wording from
`prompts/` and lays out body, notes, Sources, band and cost line with `pipeline.assemble_reply`.
The Sources list is built from chunk metadata or from the structured tool result, never from
model text, and model text is sanitised again here (idempotent after the composer callback).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from novamart_agent.models import (
    TOOL_CHECK_RETURN_ELIGIBILITY,
    TOOL_STATUS_OK,
    ConfidenceBand,
    Rubric,
)
from novamart_agent.pipeline import (
    Attempt,
    DocumentCatalog,
    ReplyKind,
    ReplyParts,
    assemble_reply,
    order_sources,
    policy_sources,
    sanitize_model_text,
)
from novamart_agent.prompts import (
    DECLINE_REPLY,
    FAILURE_REPLY,
    LOW_CONFIDENCE_NOTE,
    NOT_FOUND_REPLY,
    ORDER_RECORDS_LABEL,
    clarification_reply,
    no_answer_reply,
    not_determinable_reply,
    order_route_notes,
    weak_coverage_contact,
)


@dataclass(frozen=True)
class ReplyEnv:
    """What reply wording needs from the loaded documents: the catalog, the path label shown in
    Sources, and the escalation contact (read from a document, never hard-coded)."""

    catalog: DocumentCatalog
    docs_path_label: str
    contact: str


@dataclass(frozen=True)
class ReplyFacts:
    """The facts of one turn, read from state by the finishing node."""

    kind: ReplyKind
    composed: str
    rubric: Rubric | None
    best: Attempt | None
    order_results: Mapping[str, Mapping[str, object]]
    closest_titles: tuple[str, ...]


def _knowledge_parts(facts: ReplyFacts, env: ReplyEnv) -> ReplyParts:
    best = facts.best
    chunks = best.chunks if best else ()
    body = sanitize_model_text(facts.composed, [c.text for c in chunks])
    if best is None or not body:
        return ReplyParts(FAILURE_REPLY)
    notes = (LOW_CONFIDENCE_NOTE,) if best.band is ConfidenceBand.LOW else ()
    sources = policy_sources(chunks, env.catalog, env.docs_path_label)
    footer = (weak_coverage_contact(env.contact),) if best.band is ConfidenceBand.LOW else ()
    return ReplyParts(body, sources, best.band, notes, footer=footer)


def _order_parts(facts: ReplyFacts, env: ReplyEnv) -> ReplyParts:
    body = sanitize_model_text(facts.composed, [])
    if not body:
        return ReplyParts(FAILURE_REPLY)
    eligibility = facts.order_results.get(TOOL_CHECK_RETURN_ELIGIBILITY, {})
    answered = eligibility.get("status") == TOOL_STATUS_OK
    policy_id = eligibility.get("policy_document_id") if answered else None
    flags = facts.rubric.flags_unanswered_policy if facts.rubric else False
    extra = order_route_notes(eligibility=answered, flags_unanswered_policy=flags)
    notes = (ORDER_RECORDS_LABEL, *extra)
    sources = order_sources(policy_id, env.catalog, env.docs_path_label)
    return ReplyParts(body, sources, None, notes)


def _parts(facts: ReplyFacts, env: ReplyEnv) -> ReplyParts:
    kind = facts.kind
    if kind is ReplyKind.KNOWLEDGE_ANSWER:
        return _knowledge_parts(facts, env)
    if kind is ReplyKind.ORDER_ANSWER:
        return _order_parts(facts, env)
    if kind is ReplyKind.CLARIFY:
        slots = facts.rubric.missing_slots if facts.rubric else ()
        return ReplyParts(clarification_reply(slots))
    if kind is ReplyKind.NO_EVIDENCE:
        return ReplyParts(no_answer_reply(env.contact, facts.closest_titles))
    if kind is ReplyKind.NOT_DETERMINABLE:
        return ReplyParts(not_determinable_reply(env.contact))
    canned = {
        ReplyKind.DECLINE: DECLINE_REPLY,
        ReplyKind.NOT_FOUND: NOT_FOUND_REPLY,
    }
    return ReplyParts(canned.get(kind, FAILURE_REPLY))


def build_reply(facts: ReplyFacts, env: ReplyEnv, cost_line: str | None) -> str:
    """The text the user sees. `cost_line` is None when the display flag is off."""
    parts = _parts(facts, env)
    return assemble_reply(
        ReplyParts(parts.body, parts.sources, parts.band, parts.notes, cost_line, parts.footer)
    )
