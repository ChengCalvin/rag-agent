"""Builders for eval-kit tests: fake observations, no model, no key."""

from dataclasses import replace

from evalkit import Observation, SeededValue, ToolCall, TurnObservation
from novamart_agent.pipeline import KIND_CHAT, TurnCost, UsageRecord

NOT_FOUND = "I could not find that order, or it is not accessible to you."
COST_LINE = (
    "Cost: ~$0.0010 this answer (2 calls, 200 in / 100 out tokens) | session $0.00 over 1 question"
)


def usage(*agents: str) -> tuple[UsageRecord, ...]:
    """One chat record per agent name."""
    return tuple(UsageRecord(KIND_CHAT, a, "m", 100, 50) for a in agents)


def cost(calls: int, usd: float | None = 0.001) -> TurnCost:
    return TurnCost(usd, calls, 100 * calls, 50 * calls, 0)


def turn(
    reply: str,
    *,
    tools: tuple[str, ...] = (),
    kind: str | None = None,
    agents: tuple[str, ...] = (),
) -> TurnObservation:
    records = usage(*agents)
    return TurnObservation(
        message="q",
        reply=reply,
        tool_calls=tuple(ToolCall(t) for t in tools),
        final_kind=kind,
        usage=records,
        cost=cost(len(records)),
    )


def unpriced(observed: TurnObservation) -> TurnObservation:
    """The same turn with a model that has no price entry (cost unavailable)."""
    return replace(observed, cost=cost(observed.cost.calls, None))


def obs(
    *turns: TurnObservation, log: str = "", seeded: tuple[SeededValue, ...] = ()
) -> Observation:
    return Observation(tuple(turns), log, seeded)
