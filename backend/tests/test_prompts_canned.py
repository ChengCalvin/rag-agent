"""Canned wording (task 6.x; D13 cases A, B, C, D, F): code-produced, no policy facts inline."""

from novamart_agent.prompts import (
    DECLINE_REPLY,
    NOT_FOUND_REPLY,
    clarification_reply,
    no_answer_reply,
    not_determinable_reply,
)

CONTACT = "Operations desk (test contact)"


def test_no_answer_reply_uses_the_passed_contact_and_at_most_three_titles() -> None:
    reply = no_answer_reply(CONTACT, ["A", "B", "C", "D"])
    assert CONTACT in reply
    assert "You might mean: A; B; C." in reply
    assert "D" not in reply.split("You might mean:")[1]


def test_no_answer_reply_without_titles_has_no_you_might_mean() -> None:
    reply = no_answer_reply(CONTACT, [])
    assert "You might mean" not in reply and CONTACT in reply


def test_not_determinable_reply_carries_only_the_contact() -> None:
    assert CONTACT in not_determinable_reply(CONTACT)


def test_clarification_asks_exactly_one_question_chosen_from_a_closed_set() -> None:
    assert clarification_reply(["order_number"]).count("?") == 1
    assert clarification_reply(["something the model invented"]).count("?") == 1
    assert "invented" not in clarification_reply(["something the model invented"])


def test_the_not_found_text_is_one_constant_with_no_follow_up_question() -> None:
    assert "?" not in NOT_FOUND_REPLY
    assert "?" not in DECLINE_REPLY
