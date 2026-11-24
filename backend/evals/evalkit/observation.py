"""What one eval case produced: replies, tool calls, usage and logs (pure data, no model).

The driver fills these in from a live run; the checks read them. Customer values from the seeded
orders are carried as labelled `SeededValue`s so a failing check can name which kind of value
leaked without printing it (ERR-2: results files must hold no personal data either).
"""

import re
from dataclasses import dataclass

from novamart_agent.pipeline import KIND_CHAT, TurnCost, UsageRecord

COST_LINE_PREFIX = "Cost:"
_BAND = re.compile(r"^Confidence: (High|Medium|Low)\s*$", re.MULTILINE)
SOURCES_LABEL = "Sources:"

# final_kind (pipeline.ReplyKind value) to the refusal outcome letter of ARCH-ERR-2 (D13).
_KIND_OUTCOME = {"clarify": "A", "decline": "B", "no_evidence": "C", "not_found": "D"}


@dataclass(frozen=True)
class ToolCall:
    """One tool call the model made, in order."""

    name: str
    args: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SeededValue:
    """A customer value seeded in the synthetic orders; only the label is ever reported."""

    label: str
    text: str


@dataclass(frozen=True)
class TurnObservation:
    """One user message and what the pipeline did with it."""

    message: str
    reply: str
    tool_calls: tuple[ToolCall, ...]
    final_kind: str | None
    usage: tuple[UsageRecord, ...]
    cost: TurnCost


@dataclass(frozen=True)
class Observation:
    """All turns of one case, the captured log text and the seeded values to look for."""

    turns: tuple[TurnObservation, ...]
    log_text: str = ""
    seeded: tuple[SeededValue, ...] = ()

    def turn(self, index: int) -> TurnObservation:
        return self.turns[index]


def strip_cost_line(reply: str) -> str:
    """The reply without its trailing cost line (the line differs by session, never by cause)."""
    lines = reply.rstrip().split("\n")
    if lines and lines[-1].startswith(COST_LINE_PREFIX):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def band_of(reply: str) -> str | None:
    """`High`, `Medium` or `Low` from the code-written band line, else None."""
    match = _BAND.search(reply)
    return match.group(1) if match else None


def outcome_of(turn: TurnObservation) -> str | None:
    """The refusal outcome A to E of a turn, or None for an ordinary answer.

    E is an answer with a Low band (D13: weak coverage is not a refusal). The letter comes from
    code-written state and layout, never from the model's words.
    """
    letter = _KIND_OUTCOME.get(turn.final_kind or "")
    if letter is not None:
        return letter
    if turn.final_kind == "knowledge_answer" and band_of(turn.reply) == "Low":
        return "E"
    return None


def model_calls(turn: TurnObservation) -> int:
    """Chat-model calls of the turn (the query embedding is an estimate and not a call)."""
    return sum(1 for r in turn.usage if r.kind == KIND_CHAT)


def agents_called(turn: TurnObservation) -> tuple[str, ...]:
    """The agent of each chat call, in order."""
    return tuple(r.agent for r in turn.usage if r.kind == KIND_CHAT)


def sources_block(reply: str) -> str:
    """The text of the Sources list (from its label to the next blank line), or ''."""
    start = reply.find(SOURCES_LABEL)
    if start < 0:
        return ""
    end = reply.find("\n\n", start)
    return reply[start:] if end < 0 else reply[start:end]
