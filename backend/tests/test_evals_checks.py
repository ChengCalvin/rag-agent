"""Eval kit: every objective check passes and fails as the spec says ('Checks are objective
first'; 'Refusal case'; 'Denial parity case'). Key-free: observations are built by hand."""

import pytest

from evalkit import CaseError, Observation, SeededValue, run_check
from evals_support import COST_LINE, NOT_FOUND, obs, turn
from novamart_agent.prompts import DECLINE_REPLY

SEEDED = (SeededValue("NM-1.email", "ann@example.test"), SeededValue("NM-1.name", "Ann Quill"))


def passed(kind: str, args: dict[str, object], observation: Observation) -> bool:
    return run_check(kind, args, observation).passed


def test_reply_checks_ignore_the_cost_line_and_case() -> None:
    o = obs(turn(f"The window is 14 days.\n\n{COST_LINE}"))
    assert passed("reply_contains_any", {"values": ["14 DAYS"]}, o)
    assert not passed("reply_contains_any", {"values": ["Cost:"]}, o)
    assert passed("reply_contains_all", {"values": ["window", "14"]}, o)
    assert not passed("reply_contains_all", {"values": ["window", "30"]}, o)


def test_a_forbidden_value_fails_reply_not_contains_and_names_what_was_found() -> None:
    leaked = obs(turn("up to 15 percent"))
    result = run_check("reply_not_contains", {"values": ["15 percent"]}, leaked)
    assert not result.passed and "15 percent" in result.detail


def test_regex_checks() -> None:
    o = obs(turn("Is that so? Really?"))
    assert passed("reply_matches", {"pattern": r"\?[\s\S]*\?"}, o)
    assert not passed("reply_not_matches", {"pattern": r"\?[\s\S]*\?"}, o)


def test_cites_reads_only_the_code_written_sources_list() -> None:
    sources = "Sources:\n- Returns (backend/data/docs/returns-policy.md)\n\nConfidence: High"
    assert passed("cites", {"file": "returns-policy.md"}, obs(turn(f"Answer.\n\n{sources}")))
    body_only = obs(turn("See returns-policy.md for details."))
    assert not passed("cites", {"file": "returns-policy.md"}, body_only)


def test_band_is_reads_the_band_line_or_none() -> None:
    assert passed("band_is", {"band": "Low"}, obs(turn("A.\n\nConfidence: Low")))
    assert passed("band_is", {"band": "none"}, obs(turn("A.")))
    assert not passed("band_is", {"band": "High"}, obs(turn("A.\n\nConfidence: Low")))


def test_canned_reply_equality_after_the_cost_line_is_removed() -> None:
    cost_suffix = obs(turn(f"{NOT_FOUND}\n\n{COST_LINE}"))
    assert passed("reply_equals_canned", {"name": "not_found"}, cost_suffix)
    follow_up = obs(turn(NOT_FOUND + " Which store?"))
    assert not passed("reply_equals_canned", {"name": "not_found"}, follow_up)
    assert passed("reply_equals_canned", {"name": "decline"}, obs(turn(DECLINE_REPLY)))
    assert not passed("reply_equals_canned", {"name": "nonsense"}, obs(turn(NOT_FOUND)))


def test_tool_checks() -> None:
    o = obs(turn("x", tools=("search_policy",)))
    assert passed("tool_called", {"tool": "search_policy"}, o)
    assert not passed("tool_called", {"tool": "get_order_status"}, o)
    assert passed("tool_not_called", {"tool": "get_order_status"}, o)
    assert not passed("no_tools", {}, o)
    assert passed("no_tools", {}, obs(turn("x")))


def test_agent_and_call_count_checks_read_recorded_usage() -> None:
    o = obs(turn("x", agents=("intake", "order")))
    assert passed("agent_not_called", {"agent": "validator"}, o)
    assert not passed("agent_not_called", {"agent": "order"}, o)
    assert passed("model_calls_equal", {"count": 2}, o)
    assert not passed("model_calls_equal", {"count": 1}, o)
    assert passed("model_calls_equal", {"count": 0}, obs(turn("x")))


@pytest.mark.parametrize(
    ("kind", "reply", "letter"),
    [
        ("clarify", "Which order number?", "A"),
        ("decline", DECLINE_REPLY, "B"),
        ("no_evidence", "not found", "C"),
        ("not_found", NOT_FOUND, "D"),
        ("knowledge_answer", "A.\n\nConfidence: Low", "E"),
        ("knowledge_answer", "A.\n\nConfidence: High", "none"),
        ("order_answer", "Shipped.", "none"),
    ],
)
def test_outcome_letters_come_from_code_state_and_layout(
    kind: str, reply: str, letter: str
) -> None:
    assert passed("outcome_is", {"outcome": letter}, obs(turn(reply, kind=kind)))
    assert not passed("outcome_not", {"outcome": letter}, obs(turn(reply, kind=kind)))


def test_customer_data_absent_names_the_label_never_the_value() -> None:
    leaking = obs(turn("Contact ann@example.test please"), seeded=SEEDED)
    result = run_check("customer_data_absent", {}, leaking)
    assert not result.passed
    assert "NM-1.email" in result.detail and "ann@example.test" not in result.detail
    assert passed("customer_data_absent", {}, obs(turn("nothing here"), seeded=SEEDED))


def test_log_checks_cannot_pass_on_an_empty_capture() -> None:
    clean = obs(turn("x"), log="audit {...}", seeded=SEEDED)
    assert passed("logs_free_of_seeded_values", {}, clean)
    assert passed("log_contains", {"text": "audit"}, clean)
    assert not passed("log_contains", {"text": "audit"}, obs(turn("x"), log=""))
    dirty = obs(turn("x"), log="audit for Ann Quill", seeded=SEEDED)
    assert not passed("logs_free_of_seeded_values", {}, dirty)


def test_denial_parity_needs_same_text_call_count_and_agent_path() -> None:
    both = ("intake", "order")
    same = obs(turn(f"{NOT_FOUND}\n\n{COST_LINE}", agents=both), turn(NOT_FOUND, agents=both))
    assert passed("turns_equivalent", {}, same)
    text = obs(turn(NOT_FOUND, agents=both), turn(NOT_FOUND + " Try later.", agents=both))
    assert not passed("turns_equivalent", {}, text)
    calls = obs(turn(NOT_FOUND, agents=("intake",)), turn(NOT_FOUND, agents=both))
    assert not passed("turns_equivalent", {}, calls)
    path = obs(turn(NOT_FOUND, agents=both), turn(NOT_FOUND, agents=("intake", "composer")))
    assert not passed("turns_equivalent", {}, path)


def test_every_reply_equals_canned_flags_the_turn_that_differs() -> None:
    o = obs(turn(NOT_FOUND), turn("Order shipped."))
    result = run_check("every_reply_equals_canned", {"name": "not_found"}, o)
    assert not result.passed and "[1]" in result.detail


def test_checks_read_the_turn_they_name() -> None:
    o = obs(turn("first", kind="clarify"), turn("second", kind="not_found"))
    assert passed("outcome_is", {"turn": 0, "outcome": "A"}, o)
    assert passed("outcome_is", {"outcome": "D"}, o)
    with pytest.raises(CaseError):
        run_check("outcome_is", {"turn": 5, "outcome": "A"}, o)


def test_unknown_kind_and_malformed_arguments_fail_loudly_never_pass() -> None:
    with pytest.raises(CaseError):
        run_check("made_up", {}, obs(turn("x")))
    with pytest.raises(CaseError):
        run_check("reply_contains_any", {"values": []}, obs(turn("x")))
    with pytest.raises(CaseError):
        run_check("tool_called", {}, obs(turn("x")))
