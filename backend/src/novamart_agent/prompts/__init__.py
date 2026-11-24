"""Model instructions and canned wording, one module per agent.

Public names are exposed here (ARCH-MOD-2); other packages import only these.
"""

from novamart_agent.prompts.canned import (
    DECLINE_REPLY,
    FAILURE_REPLY,
    LOW_CONFIDENCE_NOTE,
    NOT_FOUND_REPLY,
    ORDER_LIMITATION_SENTENCE,
    ORDER_RECORDS_LABEL,
    SYNTHETIC_POLICY_NOTE,
    clarification_reply,
    no_answer_reply,
    not_determinable_reply,
    order_route_notes,
)
from novamart_agent.prompts.composer import COMPOSER_INSTRUCTION
from novamart_agent.prompts.intake import INTAKE_INSTRUCTION
from novamart_agent.prompts.order import ORDER_INSTRUCTION
from novamart_agent.prompts.retrieval import RETRIEVAL_INSTRUCTION
from novamart_agent.prompts.validator import VALIDATOR_INSTRUCTION

__all__: list[str] = [
    "COMPOSER_INSTRUCTION",
    "DECLINE_REPLY",
    "FAILURE_REPLY",
    "INTAKE_INSTRUCTION",
    "LOW_CONFIDENCE_NOTE",
    "NOT_FOUND_REPLY",
    "ORDER_INSTRUCTION",
    "ORDER_LIMITATION_SENTENCE",
    "ORDER_RECORDS_LABEL",
    "RETRIEVAL_INSTRUCTION",
    "SYNTHETIC_POLICY_NOTE",
    "VALIDATOR_INSTRUCTION",
    "clarification_reply",
    "no_answer_reply",
    "not_determinable_reply",
    "order_route_notes",
]
