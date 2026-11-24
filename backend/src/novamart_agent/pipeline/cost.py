"""Cost per turn and per session, computed by code from recorded usage (task 6.5, D17, AGENT-5).

Pure: no clock, no I/O. A `UsageRecord` is what a model call returned (token counts only: no
message text, no personal data, ERR-2). Prices come from configuration by model ID; a model with
no price makes the turn "cost unavailable" (`usd` is None), never zero. Recording does not
depend on the display flag. `calls` counts chat-model calls; the query embedding is an
estimate that adds to the price but not to the call count or the chat token totals.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from novamart_agent.config import ModelPrice
from novamart_agent.errors import CostRecordError

UsageKind = Literal["chat", "embedding"]
KIND_CHAT: Final = "chat"
KIND_EMBEDDING: Final = "embedding"
_KINDS: Final[Mapping[str, UsageKind]] = {KIND_CHAT: KIND_CHAT, KIND_EMBEDDING: KIND_EMBEDDING}
_TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class UsageRecord:
    """One model call. For chat, `output_tokens` includes thinking tokens (D17)."""

    kind: UsageKind
    agent: str
    model_id: str
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict[str, object]:
        """The JSON-safe form stored in session state."""
        return {
            "kind": self.kind,
            "agent": self.agent,
            "model_id": self.model_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(frozen=True)
class TurnCost:
    """The cost of one user question. `usd` is None when any model used has no price."""

    usd: float | None
    calls: int
    input_tokens: int
    output_tokens: int
    embedding_tokens: int


@dataclass(frozen=True)
class SessionCost:
    """Running total. `usd` sums the priced turns; `unpriced_questions` counts the others."""

    usd: float = 0.0
    questions: int = 0
    unpriced_questions: int = 0


def _count(entry: Mapping[str, object], key: str) -> int:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CostRecordError(f"usage record field '{key}' must be a non-negative integer")
    return value


def _text(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        raise CostRecordError(f"usage record field '{key}' must be a non-empty string")
    return value


def parse_usage_records(raw: object) -> tuple[UsageRecord, ...]:
    """Type the per-turn list kept in session state (None or absent means no calls)."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CostRecordError("usage records must be a list")
    records: list[UsageRecord] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise CostRecordError("usage record must be an object")
        kind = _KINDS.get(_text(entry, "kind"))
        if kind is None:
            raise CostRecordError("usage record field 'kind' is unknown")
        records.append(
            UsageRecord(
                kind,
                _text(entry, "agent"),
                _text(entry, "model_id"),
                _count(entry, "input_tokens"),
                _count(entry, "output_tokens"),
            )
        )
    return tuple(records)


@dataclass(frozen=True)
class TokenCounts:
    """A response's `usage_metadata` counts; an absent count is None (read as 0)."""

    prompt: int | None = None
    candidate: int | None = None
    thought: int | None = None


def chat_usage_record(agent: str, model_id: str, counts: TokenCounts) -> UsageRecord:
    """Build a chat record from a response's token counts.

    Thinking tokens are billed as output, so they are summed into `output_tokens` (D17).
    """
    prompt, candidate, thought = (c or 0 for c in (counts.prompt, counts.candidate, counts.thought))
    if min(prompt, candidate, thought) < 0:
        raise CostRecordError("token counts must be non-negative")
    return UsageRecord(KIND_CHAT, agent, model_id, prompt, candidate + thought)


def _record_usd(record: UsageRecord, price: ModelPrice) -> float:
    return (
        record.input_tokens * price.input_per_m + record.output_tokens * price.output_per_m
    ) / _TOKENS_PER_MILLION


def compute_turn_cost(records: Sequence[UsageRecord], prices: Mapping[str, ModelPrice]) -> TurnCost:
    """Sum every record of one turn. No records is a priced turn costing $0.00 (a decline)."""
    usd: float | None = 0.0
    for record in records:
        price = prices.get(record.model_id)
        usd = None if price is None or usd is None else usd + _record_usd(record, price)
    chat = [r for r in records if r.kind == KIND_CHAT]
    return TurnCost(
        usd,
        len(chat),
        sum(r.input_tokens for r in chat),
        sum(r.output_tokens for r in chat),
        sum(r.input_tokens for r in records if r.kind == KIND_EMBEDDING),
    )


def add_turn(session: SessionCost, turn: TurnCost) -> SessionCost:
    """The session total after one more answered question."""
    if turn.usd is None:
        return SessionCost(session.usd, session.questions + 1, session.unpriced_questions + 1)
    return SessionCost(session.usd + turn.usd, session.questions + 1, session.unpriced_questions)


def embedding_billed(result: Mapping[str, object]) -> bool:
    """Whether a `search_policy` result means a billed query-embedding call was made.

    Reads the tool's explicit `embedded` field: True only when the embedding API was called for
    this query (never for a blocked query, a cache hit or an error).
    """
    return result.get("embedded") is True


def embedding_estimate(
    result: Mapping[str, object], query: object, model_id: str, chars_per_token: int
) -> UsageRecord | None:
    """The estimated embedding usage for one search, or None when none was billed.

    The token count is estimated from the query length (AI Studio may not return embedding
    token counts, D17); only the count is kept, never the query text.
    """
    if not embedding_billed(result) or not isinstance(query, str) or not query.strip():
        return None
    tokens = max(1, math.ceil(len(query.strip()) / chars_per_token))
    return UsageRecord(KIND_EMBEDDING, "retrieval", model_id, tokens, 0)
