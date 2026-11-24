"""Output schemas of the two agents that return a record (task 7.2, 7.3, D10, D11).

They only shape what the model is asked to produce (ADK enforces the JSON shape). What comes
back is still untrusted data: `pipeline.parse_rubric` and `pipeline.parse_verdict` re-read it
into the typed models, so a value the schema allows is never trusted by being in the schema.
"""

from typing import Literal

from pydantic import BaseModel


class CriterionSchema(BaseModel):
    """One checkable part of the user's intent."""

    text: str
    required: bool
    unanswered_policy: bool = False


class RubricSchema(BaseModel):
    """What intake returns."""

    route: Literal["order", "knowledge", "clarify", "oos"]
    doc_type: Literal["policy", "product"] | None = None  # ADK drops None before re-validating
    criteria: list[CriterionSchema]
    missing_slots: list[str] = []


class VerdictSchema(BaseModel):
    """What the validator returns."""

    coverage: list[bool]
    llm_confidence: float
    rewritten_query: str | None = None
