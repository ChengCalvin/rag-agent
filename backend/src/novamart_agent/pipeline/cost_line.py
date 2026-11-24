"""The cost line text (task 6.5, D17). Display only: the flag never stops recording.

Shape: `Cost: ~$0.0021 this answer (5 calls, 3,840 in / 410 out tokens) | session ~$0.0187 over
9 questions`. A precheck decline reads `$0.00 (0 calls)`. An unpriced model reads "cost
unavailable", never $0. The first reply of a session adds the "API-equivalent estimate, not
billed" label, once.
"""

from novamart_agent.pipeline.cost import SessionCost, TurnCost

UNAVAILABLE = "cost unavailable"
FIRST_REPLY_LABEL = "API-equivalent estimate, not billed"


def _money(usd: float) -> str:
    return "$0.00" if usd == 0 else f"~${usd:.4f}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _turn_part(turn: TurnCost) -> str:
    amount = UNAVAILABLE if turn.usd is None else _money(turn.usd)
    if turn.calls == 0:
        detail = "(0 calls)"
    else:
        detail = (
            f"({_plural(turn.calls, 'call')}, {turn.input_tokens:,} in / "
            f"{turn.output_tokens:,} out tokens)"
        )
    return f"{amount} this answer {detail}"


def _session_part(session: SessionCost) -> str:
    questions = _plural(session.questions, "question")
    if session.unpriced_questions == session.questions:
        return f"session {UNAVAILABLE} over {questions}"
    excluded = (
        f" (excludes {session.unpriced_questions} with {UNAVAILABLE})"
        if session.unpriced_questions
        else ""
    )
    return f"session {_money(session.usd)} over {questions}{excluded}"


def render_cost_line(turn: TurnCost, session: SessionCost) -> str:
    """The line for one answer. `session` already includes this turn, so the first reply of a
    session is the one with `session.questions == 1`."""
    line = f"Cost: {_turn_part(turn)} | {_session_part(session)}"
    return f"{line} | {FIRST_REPLY_LABEL}" if session.questions == 1 else line


def cost_line_if_shown(turn: TurnCost, session: SessionCost, show_cost: bool) -> str | None:
    """The line when `NOVAMART_SHOW_COST` is on, else None."""
    return render_cost_line(turn, session) if show_cost else None
