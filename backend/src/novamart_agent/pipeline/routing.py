"""Routing from the rubric (task 6.2, D10, D13).

A pure function of the rubric and the clarification counter: the route is never a model
decision about which agent runs next. The rubric is the only input, so a malformed order id in
the user's words cannot change the route (AG-43): intake marks it `order` and the order tool
rejects it.
"""

from dataclasses import dataclass
from enum import StrEnum

from novamart_agent.models import Route, Rubric


class TurnRoute(StrEnum):
    """The values the `route_turn` function node can emit; each needs an edge (task 7.3)."""

    ORDER = "order"
    KNOWLEDGE = "knowledge"
    CLARIFY = "clarify"
    DECLINE = "decline"


@dataclass(frozen=True)
class RoutingDecision:
    """The route and the clarification counter to store after this turn."""

    route: TurnRoute
    clarifications_asked: int


def route_turn(rubric: Rubric, clarifications_asked: int, cap: int) -> RoutingDecision:
    """Pick the route. A clarify request is honoured while fewer than `cap` questions have been
    asked for this user question; beyond the cap the turn proceeds with best effort as a
    knowledge question (case A, D13), where the deterministic gate still refuses without
    evidence. Any route other than a clarification ends the question, so the counter resets."""
    if rubric.route is Route.CLARIFY:
        if clarifications_asked < cap:
            return RoutingDecision(TurnRoute.CLARIFY, clarifications_asked + 1)
        return RoutingDecision(TurnRoute.KNOWLEDGE, 0)
    if rubric.route is Route.ORDER:
        return RoutingDecision(TurnRoute.ORDER, 0)
    if rubric.route is Route.OOS:
        return RoutingDecision(TurnRoute.DECLINE, 0)
    return RoutingDecision(TurnRoute.KNOWLEDGE, 0)
