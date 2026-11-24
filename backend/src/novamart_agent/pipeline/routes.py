"""Route values and reply kinds the function nodes emit (task 7.2, 7.3).

Every route value a node can emit is a member of one of these enums (or `TurnRoute` /
`LoopRoute`), so a test can check that each has an edge in the graph. `ReplyKind` is the closed
set of final replies (ERR-3): the outcomes A to E of `ARCH-ERR-2`, the not-determinable reply
(case F), the generic failure, and the two composed answers.
"""

from enum import StrEnum


class PrecheckRoute(StrEnum):
    """What the `precheck` node emits."""

    PROCEED = "proceed"
    DECLINE = "decline"


class AfterRetrievalRoute(StrEnum):
    """What the `after_retrieval` node emits."""

    VALIDATE = "validate"
    REFUSE = "refuse"
    COMPOSE = "compose"  # a retry found nothing, but an earlier pass has evidence to compose from


class AfterOrderRoute(StrEnum):
    """What the `after_order` node emits."""

    COMPOSE = "compose"
    FINAL = "final"


class ReplyKind(StrEnum):
    """The kind of the final reply; each has one observable output (D13)."""

    CLARIFY = "clarify"  # A
    DECLINE = "decline"  # B
    NO_EVIDENCE = "no_evidence"  # C
    NOT_FOUND = "not_found"  # D
    NOT_DETERMINABLE = "not_determinable"  # F
    FAILURE = "failure"  # generic, not an outcome A to E (ARCH-ERR-1)
    KNOWLEDGE_ANSWER = "knowledge_answer"  # E when the band is Low
    ORDER_ANSWER = "order_answer"
