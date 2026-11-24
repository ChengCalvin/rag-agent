"""Canned wording produced by code, never by a model (ARCH-CFG-2, D13, D14, D15).

Declines, the clarification question, the no-evidence and not-determinable replies, the uniform
not-found text, the limitation sentence and the synthetic-policy note. No policy fact lives
here: the escalation contact and document titles are passed in (the contact comes from the
store operations document front-matter via `rag.escalation_contact`).
"""

from collections.abc import Sequence

DECLINE_REPLY = (
    "I can only help with NovaMart store questions: company policies, product information, "
    "and the status or return eligibility of orders you can access. Please ask about one of those."
)

# One text for every denial cause (nonexistent, out of scope, malformed, throttled): the reply
# must not reveal why (ARCH-ERR-1, D13 case D). No follow-up question is ever added to it.
NOT_FOUND_REPLY = "I could not find that order, or it is not accessible to you."

ORDER_LIMITATION_SENTENCE = (
    "I could only answer the order part of your question here. I cannot answer the policy part "
    "in the same message, so please ask it as a separate question."
)

SYNTHETIC_POLICY_NOTE = (
    "Note: this is a demonstration assistant. The return policy it applies is invented sample "
    "data, not a real NovaMart policy or a real return entitlement."
)

# Generic failure (ARCH-ERR-1): a tool or the pipeline failed. Fixed text, never model-written;
# it carries no cause and no personal data.
FAILURE_REPLY = "Something went wrong while handling that. Please try again in a moment."

# Added by code when the confidence band is Low (D13 case E); the model never writes it.
LOW_CONFIDENCE_NOTE = (
    "Note: the documents may not fully cover this question, so please check the sources "
    "below before relying on this answer."
)

# Labels the order route (D14): the facts come from the order system, not from documents.
ORDER_RECORDS_LABEL = "From order records."

_GENERIC_CLARIFICATION = "Could you tell me a little more about what you need?"
_SLOT_QUESTIONS: dict[str, str] = {
    "order_number": "Which order number do you mean? It looks like NM- followed by six digits.",
    "product": "Which product do you mean?",
}


def clarification_reply(missing_slots: Sequence[str]) -> str:
    """Exactly one question. The wording is chosen from a closed set by the first known slot;
    model-written slot text is never echoed (it is untrusted data)."""
    for slot in missing_slots:
        if slot in _SLOT_QUESTIONS:
            return _SLOT_QUESTIONS[slot]
    return _GENERIC_CLARIFICATION


def no_answer_reply(contact: str, closest_titles: Sequence[str]) -> str:
    """Case C: nothing found, ask a new question, give the contact, name up to three titles
    that already passed the audience filter."""
    text = (
        "I could not find that in NovaMart's documents. Please ask a new question, or contact "
        f"{contact}."
    )
    if closest_titles:
        return f"{text} You might mean: {'; '.join(closest_titles[:3])}."
    return text


def not_determinable_reply(contact: str) -> str:
    """Case F: eligibility cannot be determined; give the contact; nothing else."""
    return f"I cannot determine return eligibility for this order. Please contact {contact}."


def order_route_notes(*, eligibility: bool, flags_unanswered_policy: bool) -> tuple[str, ...]:
    """Notes appended after an order-route body: the synthetic-policy note on an eligibility
    answer (compliance F2), and the limitation sentence when intake flagged a policy part."""
    notes: list[str] = []
    if eligibility:
        notes.append(SYNTHETIC_POLICY_NOTE)
    if flags_unanswered_policy:
        notes.append(ORDER_LIMITATION_SENTENCE)
    return tuple(notes)
