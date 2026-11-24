"""One turn's cost and the new session total, from the usage records in state (task 7.6, D17).

Pure. Recording does not depend on the display flag: `line` is None only when the flag is off,
and the session total is updated either way (AGENT-5).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from novamart_agent.config import ModelPrice
from novamart_agent.pipeline.cost import (
    SessionCost,
    TurnCost,
    UsageRecord,
    add_turn,
    compute_turn_cost,
    parse_usage_records,
)
from novamart_agent.pipeline.cost_line import cost_line_if_shown


@dataclass(frozen=True)
class TurnAccount:
    """The turn's cost, the session total including it, and the display line (or None)."""

    turn: TurnCost
    session: SessionCost
    line: str | None


def account_turn(
    raw_records: object,
    session: SessionCost,
    prices: Mapping[str, ModelPrice],
    show_cost: bool,
) -> TurnAccount:
    """Cost the turn's records, add it to `session` and render the line when shown."""
    turn = compute_turn_cost(parse_usage_records(raw_records), prices)
    updated = add_turn(session, turn)
    return TurnAccount(turn, updated, cost_line_if_shown(turn, updated, show_cost))


def with_usage(raw_records: object, record: UsageRecord) -> list[dict[str, object]]:
    """The per-turn usage list with `record` added (the old list is validated, never mutated)."""
    return [r.to_dict() for r in (*parse_usage_records(raw_records), record)]
