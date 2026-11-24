"""Tasks 7.4, 7.6: the order route under ADK with scripted models (no key).

Covers the halt at a deterministic tool result (no summarising call), denial parity across the
three causes, the Sources entry from the tool result and the not-determinable reply.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from novamart_agent.prompts import NOT_FOUND_REPLY, not_determinable_reply
from novamart_agent.rag import escalation_contact, load_documents
from stub_llm import call, call_together, say, say_json, scripted
from world import Scripts, WorldOptions, build_world, flag_unanswered_policy, rubric_json, unused

ORDER_RUBRIC = rubric_json("order", (("order status or return", True),))


def order_scripts(*steps_order: object, composer: str | None = None) -> Scripts:
    return Scripts(
        intake=scripted("intake", say_json(ORDER_RUBRIC)),
        retrieval=unused("retrieval"),
        validator=unused("validator"),
        order=scripted("order", *steps_order),  # type: ignore[arg-type]
        composer=scripted("composer", say(composer)) if composer else unused("composer"),
    )


def body_of(reply: str) -> str:
    """The reply without the cost line."""
    return reply.split("\n\nCost:")[0]


# ------------------------------------------------- denial parity (requirement)


@pytest.mark.parametrize(
    ("cause", "order_id"),
    [("nonexistent", "NM-999999"), ("out of scope", "NM-480201"), ("malformed", "10x2")],
)
def test_denials_do_not_reveal_existence_equal_calls_and_the_same_code_text(
    data_dir: Path, tmp_path: Path, cause: str, order_id: str
) -> None:
    """Cost does not reveal why an order was denied: the same text and the same whole-turn
    model calls (intake, one order call, nothing after the tool result) for every cause.
    A malformed id is routed to `order` by intake, never to `clarify`."""
    scripts = order_scripts(call("get_order_status", order_id=order_id))
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run(f"Status of {order_id}?")
    assert body_of(turn.reply) == NOT_FOUND_REPLY, cause
    assert (scripts.intake.calls, scripts.order.calls) == (1, 1)
    assert scripts.composer.calls == scripts.retrieval.calls == scripts.validator.calls == 0
    assert scripts.calls() == 2
    assert "(2 calls," in turn.reply


def test_the_three_denial_replies_are_identical_including_the_cost_line(
    data_dir: Path, tmp_path: Path
) -> None:
    replies = set()
    for index, order_id in enumerate(("NM-999999", "NM-480201", "10x2")):
        scripts = order_scripts(call("get_order_status", order_id=order_id))
        world = build_world(scripts, data_dir, tmp_path / f"c{index}")
        (turn,) = world.run("Where is my order?")  # the same message text for every cause
        replies.add(turn.reply)
    assert len(replies) == 1


def test_a_throttled_session_gets_the_same_denial_with_the_same_calls(
    data_dir: Path, tmp_path: Path
) -> None:
    ids = ["NM-999991", "NM-999992", "NM-999993", "NM-999994", "NM-999995", "NM-480101"]
    intake_steps = [say_json(ORDER_RUBRIC)] * len(ids)
    scripts = Scripts(
        intake=scripted("intake", *intake_steps),
        retrieval=unused("r"),
        validator=unused("v"),
        order=scripted("order", *[call("get_order_status", order_id=i) for i in ids]),
        composer=unused("c"),
    )
    turns = build_world(scripts, data_dir, tmp_path / "c").run(*["Where is it?"] * len(ids))
    # The sixth lookup is a valid, in-scope order, but the session is throttled: still denied.
    assert body_of(turns[-1].reply) == NOT_FOUND_REPLY
    assert scripts.order.calls == len(ids)


# --------------------------------------------------------------- answers


def test_the_order_route_shows_sources_with_title_and_path_and_no_heading(
    data_dir: Path, tmp_path: Path
) -> None:
    """Order-route Sources: the policy id comes from the tool result and resolves to title and
    path; there is no section heading."""
    scripts = order_scripts(
        call("check_return_eligibility", order_id="NM-480101"), composer="Yes, you can return it."
    )
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run("Can I return NM-480101?")
    entry = "- Returns and Refunds Policy (backend/data/docs/returns-policy.md)"
    assert f"Sources:\n{entry}" in turn.reply
    assert "section" not in turn.reply
    assert "From order records." in turn.reply
    assert "Confidence:" not in turn.reply
    assert scripts.calls() == 3  # intake, order (halted at the result), composer


def test_the_sources_id_comes_from_the_tool_result_not_from_model_text(
    data_dir: Path, tmp_path: Path
) -> None:
    fabricated = (
        "Yes. See manager-approvals.\n\nSources:\n- Made Up Policy (backend/data/docs/fake.md)\n"
        "Confidence: High"
    )
    eligibility = call("check_return_eligibility", order_id="NM-480101")
    scripts = order_scripts(eligibility, composer=fabricated)
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run("Can I return NM-480101?")
    assert "Made Up Policy" not in turn.reply
    assert "fake.md" not in turn.reply
    assert "Confidence" not in turn.reply
    assert "returns-policy.md" in turn.reply


def test_a_status_lookup_has_no_sources_entry_and_no_band(data_dir: Path, tmp_path: Path) -> None:
    scripts = order_scripts(call("get_order_status", order_id="NM-480103"), composer="In transit.")
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run("Where is NM-480103?")
    assert "Sources:" not in turn.reply
    assert "Confidence:" not in turn.reply
    assert "In transit." in turn.reply


def test_a_flagged_policy_part_gets_the_fixed_limitation_sentence(
    data_dir: Path, tmp_path: Path
) -> None:
    rubric = flag_unanswered_policy(rubric_json("order", (("return eligibility", True),)))
    scripts = Scripts(
        intake=scripted("intake", say_json(rubric)),
        retrieval=unused("r"),
        validator=unused("v"),
        order=scripted("order", call("check_return_eligibility", order_id="NM-480101")),
        composer=scripted("composer", say("Eligible.")),
    )
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run("Return NM-480101 and gift cards?")
    assert "I could only answer the order part of your question here." in turn.reply


def test_both_order_tools_called_in_one_step_are_both_kept_for_the_composer(
    data_dir: Path, tmp_path: Path
) -> None:
    both = call_together(
        ("get_order_status", {"order_id": "NM-480101"}),
        ("check_return_eligibility", {"order_id": "NM-480101"}),
    )
    scripts = order_scripts(both, composer="Delivered and returnable.")
    (turn,) = build_world(scripts, data_dir, tmp_path / "c").run("Status of NM-480101 and return?")
    assert "Delivered and returnable." in turn.reply
    assert "returns-policy.md" in turn.reply
    assert scripts.order.calls == 1
    record = scripts.composer.requests[0]
    assert "order_status" in record
    assert "policy_document_id" in record


def test_not_determinable_gives_canned_text_plus_the_contact_with_no_call_after_the_tool(
    data_dir: Path, tmp_path: Path
) -> None:
    documents = load_documents(data_dir / "docs")
    broken = tuple(
        replace(d, metadata={}) if d.doc_id == "returns-policy" else d for d in documents
    )
    scripts = order_scripts(call("check_return_eligibility", order_id="NM-480101"))
    world = build_world(scripts, data_dir, tmp_path / "c", WorldOptions(documents=broken))
    (turn,) = world.run("Can I return NM-480101?")
    assert body_of(turn.reply) == not_determinable_reply(escalation_contact(documents))
    assert scripts.order.calls == 1
    assert scripts.composer.calls == 0
