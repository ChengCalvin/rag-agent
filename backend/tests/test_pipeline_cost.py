"""Task 6.5: per-turn and per-session cost, computed by code (D17, AGENT-5, spec cost-reporting)."""

import pytest

from novamart_agent.config import ModelPrice
from novamart_agent.errors import CostRecordError
from novamart_agent.pipeline import (
    FIRST_REPLY_LABEL,
    KIND_CHAT,
    KIND_EMBEDDING,
    UNAVAILABLE,
    SessionCost,
    TokenCounts,
    UsageRecord,
    add_turn,
    chat_usage_record,
    compute_turn_cost,
    cost_line_if_shown,
    embedding_billed,
    embedding_estimate,
    parse_usage_records,
    render_cost_line,
)

PRICES = {
    "chat-a": ModelPrice(1.0, 2.0),
    "embed-a": ModelPrice(0.5, 0.0),
}


def chat(agent: str, tokens_in: int, tokens_out: int, model: str = "chat-a") -> UsageRecord:
    return UsageRecord(KIND_CHAT, agent, model, tokens_in, tokens_out)


# --- turn cost ------------------------------------------------------------------------------


def test_a_rewrite_turn_sums_every_call_including_the_rewrite_pass() -> None:
    first_pass = [chat("intake", 1000, 100), chat("retrieval", 800, 50), chat("validator", 900, 60)]
    rewrite_pass = [chat("retrieval", 820, 50), chat("validator", 950, 70)]
    composer = [chat("composer", 1200, 300)]
    one_pass = compute_turn_cost(first_pass + composer, PRICES)
    with_rewrite = compute_turn_cost(first_pass + rewrite_pass + composer, PRICES)
    assert (one_pass.calls, with_rewrite.calls) == (4, 6)
    assert with_rewrite.input_tokens == 1000 + 800 + 900 + 820 + 950 + 1200
    assert with_rewrite.output_tokens == 100 + 50 + 60 + 50 + 70 + 300
    expected = (with_rewrite.input_tokens * 1.0 + with_rewrite.output_tokens * 2.0) / 1_000_000
    assert with_rewrite.usd == pytest.approx(expected)
    assert with_rewrite.usd is not None and one_pass.usd is not None
    assert with_rewrite.usd > one_pass.usd


def test_a_precheck_decline_costs_zero_dollars_with_zero_calls() -> None:
    turn = compute_turn_cost([], PRICES)
    assert (turn.usd, turn.calls) == (0.0, 0)
    line = render_cost_line(turn, add_turn(SessionCost(), turn))
    assert line.startswith("Cost: $0.00 this answer (0 calls)")


def test_the_query_embedding_adds_to_price_but_not_to_chat_calls_or_tokens() -> None:
    base = compute_turn_cost([chat("composer", 1000, 100)], PRICES)
    embedded = compute_turn_cost(
        [chat("composer", 1000, 100), UsageRecord(KIND_EMBEDDING, "retrieval", "embed-a", 200, 0)],
        PRICES,
    )
    assert embedded.calls == base.calls == 1
    assert embedded.input_tokens == base.input_tokens
    assert embedded.embedding_tokens == 200
    assert embedded.usd is not None and base.usd is not None
    assert embedded.usd - base.usd == pytest.approx(200 * 0.5 / 1_000_000)


def test_a_model_with_no_price_entry_is_cost_unavailable_never_zero() -> None:
    turn = compute_turn_cost([chat("intake", 10, 5, model="unpriced")], PRICES)
    assert turn.usd is None
    session = add_turn(SessionCost(), turn)
    line = render_cost_line(turn, session)
    assert UNAVAILABLE in line
    assert "$0" not in line
    assert (session.usd, session.questions, session.unpriced_questions) == (0.0, 1, 1)


def test_one_unpriced_call_makes_the_whole_turn_unavailable() -> None:
    turn = compute_turn_cost([chat("a", 1, 1), chat("b", 1, 1, model="unpriced")], PRICES)
    assert turn.usd is None and turn.calls == 2


# --- session ---------------------------------------------------------------------------------


def test_two_turns_sum_into_the_session_total() -> None:
    first = compute_turn_cost([chat("composer", 1000, 100)], PRICES)
    second = compute_turn_cost([chat("composer", 3000, 400)], PRICES)
    assert first.usd is not None and second.usd is not None
    session = add_turn(add_turn(SessionCost(), first), second)
    assert session.questions == 2
    assert session.usd == pytest.approx(first.usd + second.usd)
    assert f"session ~${session.usd:.4f} over 2 questions" in render_cost_line(second, session)


def test_a_new_session_starts_at_zero() -> None:
    assert SessionCost() == SessionCost(0.0, 0, 0)


def test_session_notes_unpriced_questions_it_could_not_add() -> None:
    priced = compute_turn_cost([chat("a", 1000, 100)], PRICES)
    unpriced = compute_turn_cost([chat("a", 1, 1, model="unpriced")], PRICES)
    session = add_turn(add_turn(SessionCost(), priced), unpriced)
    assert session.usd == priced.usd and session.unpriced_questions == 1
    assert f"excludes 1 with {UNAVAILABLE}" in render_cost_line(unpriced, session)


# --- the line --------------------------------------------------------------------------------


def test_the_line_shows_cost_calls_tokens_and_session_total() -> None:
    turn = compute_turn_cost([chat("a", 3000, 400), chat("b", 840, 10)], PRICES)
    line = render_cost_line(turn, SessionCost(0.0187, 9, 0))
    assert line.startswith("Cost: ~$0.0")
    assert "this answer (2 calls, 3,840 in / 410 out tokens)" in line
    assert line.endswith("session ~$0.0187 over 9 questions")


def test_api_equivalent_label_appears_once_on_the_first_reply_only() -> None:
    turn = compute_turn_cost([chat("a", 10, 10)], PRICES)
    first = add_turn(SessionCost(), turn)
    second = add_turn(first, turn)
    assert FIRST_REPLY_LABEL in render_cost_line(turn, first)
    assert FIRST_REPLY_LABEL not in render_cost_line(turn, second)


def test_flag_on_shows_the_line_and_flag_off_hides_only_the_display() -> None:
    turn = compute_turn_cost([chat("a", 10, 10)], PRICES)
    session = add_turn(SessionCost(), turn)
    assert cost_line_if_shown(turn, session, True) == render_cost_line(turn, session)
    assert cost_line_if_shown(turn, session, False) is None
    assert session.questions == 1 and turn.calls == 1  # the record is unaffected by the flag


# Denial parity (same tool result for nonexistent, out-of-scope and malformed ids) is tested
# against the real order tool in test_pipeline_qa_chunk6.py and test_tools_*.py.

# --- thinking tokens count as output ----------------------------------------------------------


def test_thinking_tokens_are_summed_into_output_tokens() -> None:
    record = chat_usage_record("composer", "chat-a", TokenCounts(1000, 200, 300))
    assert record == UsageRecord(KIND_CHAT, "composer", "chat-a", 1000, 500)
    priced = compute_turn_cost([record], PRICES)
    assert priced.output_tokens == 500
    assert priced.usd == pytest.approx((1000 * 1.0 + 500 * 2.0) / 1_000_000)


def test_missing_token_counts_are_zero_and_negative_counts_fail_loudly() -> None:
    assert chat_usage_record("a", "chat-a", TokenCounts()) == chat("a", 0, 0)
    assert chat_usage_record("a", "chat-a", TokenCounts(7, 3)) == chat("a", 7, 3)
    with pytest.raises(CostRecordError):
        chat_usage_record("a", "chat-a", TokenCounts(1, -1, 0))


# --- usage records in session state ------------------------------------------------------------


def test_usage_records_round_trip_through_session_state() -> None:
    records = [chat("intake", 5, 6), UsageRecord(KIND_EMBEDDING, "retrieval", "embed-a", 9, 0)]
    assert parse_usage_records([r.to_dict() for r in records]) == tuple(records)
    assert parse_usage_records(None) == ()


@pytest.mark.parametrize(
    "bad",
    [
        "x",
        [1],
        [{"kind": "chat"}],
        [{"kind": "other", "agent": "a", "model_id": "m", "input_tokens": 1, "output_tokens": 1}],
        [{"kind": "chat", "agent": "a", "model_id": "m", "input_tokens": -1, "output_tokens": 1}],
        [{"kind": "chat", "agent": "a", "model_id": "m", "input_tokens": True, "output_tokens": 1}],
    ],
)
def test_malformed_usage_records_fail_loudly(bad: object) -> None:
    with pytest.raises(CostRecordError):
        parse_usage_records(bad)


def test_a_record_carries_only_counts_and_ids_no_message_text() -> None:
    record = chat("composer", 1, 2)
    assert set(record.to_dict()) == {"kind", "agent", "model_id", "input_tokens", "output_tokens"}


# --- embedding estimate decision: the tool's explicit `embedded` field --------------------------

QUERY = "how long do customers have to return opened electronics"
OK_MISS = {"status": "ok", "embedding_cache_hit": False, "embedded": True, "chunks": []}
OK_HIT = {"status": "ok", "embedding_cache_hit": True, "embedded": False, "chunks": []}
NO_ANSWER_MISS = {
    "status": "no_answer",
    "embedding_cache_hit": False,
    "embedded": True,
    "closest_titles": ["R"],
}
NO_ANSWER_HIT = {**NO_ANSWER_MISS, "embedding_cache_hit": True, "embedded": False}
# A real search over an empty permitted corpus: the call was made, nothing was found (QA6-3).
EMPTY_CORPUS_RESULT = {**NO_ANSWER_MISS, "closest_titles": []}
# What the tool returns for a blank or over-long query, and for a caller with no principal.
BLANK_QUERY_RESULT = {
    "status": "no_answer",
    "embedding_cache_hit": False,
    "embedded": False,
    "closest_titles": [],
}
NO_PRINCIPAL_RESULT = dict(BLANK_QUERY_RESULT)
ERROR_RESULT = {"status": "error", "embedding_cache_hit": False, "embedded": False}


@pytest.mark.parametrize(
    ("result", "billed"),
    [
        (OK_MISS, True),
        (OK_HIT, False),
        (NO_ANSWER_MISS, True),  # a no_answer on a cache miss still embedded once
        (NO_ANSWER_HIT, False),
        (EMPTY_CORPUS_RESULT, True),  # real call, no chunks, no titles: still billed
        (BLANK_QUERY_RESULT, False),  # blank or over-long query: no embedding call was made
        (NO_PRINCIPAL_RESULT, False),  # no principal: deny by default, no embedding call
        (ERROR_RESULT, False),
        ({"status": "ok"}, False),  # no explicit field: never inferred
        ({}, False),
    ],
)
def test_embedding_is_costed_only_for_a_real_uncached_embedding(
    result: dict[str, object], billed: bool
) -> None:
    assert embedding_billed(result) is billed
    estimate = embedding_estimate(result, QUERY, "embed-a", 4)
    assert (estimate is not None) is billed


def test_the_estimate_is_one_embedding_record_from_query_length_without_the_text() -> None:
    estimate = embedding_estimate(OK_MISS, "a" * 41, "embed-a", 4)
    assert estimate == UsageRecord(KIND_EMBEDDING, "retrieval", "embed-a", 11, 0)
    assert "a" * 5 not in repr(estimate)


@pytest.mark.parametrize("query", ["", "   ", None, 5])
def test_no_estimate_without_a_usable_query_text(query: object) -> None:
    assert embedding_estimate(OK_MISS, query, "embed-a", 4) is None
