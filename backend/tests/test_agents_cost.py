"""Task 7.6: cost capture and display across every outcome (requirement 'Cost does not reveal why
an order was denied'; D17). Key-free: scripted models, real graph, real callbacks."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from novamart_agent.pipeline import STATE_SESSION_COST, STATE_USAGE
from novamart_agent.rag import load_documents
from stub_llm import call, say, say_json, scripted
from world import Scripts, World, WorldOptions, build_world, rubric_json, unused, verdict_json

ORDER = rubric_json("order", (("order", True),))
POLICY = rubric_json("knowledge", (("window", True),), doc_type="policy")
STRONG = "returns refund window days policy"
WEAK = "xylophone zebra"


def scripts_with(**models: object) -> Scripts:
    defaults = {n: unused(n) for n in ("intake", "retrieval", "validator", "order", "composer")}
    return Scripts(**{**defaults, **models})  # type: ignore[arg-type]


def outcome_a() -> Scripts:
    rubric = rubric_json("clarify", (("which order", True),), slots=("order_number",))
    return scripts_with(intake=scripted("intake", say_json(rubric)))


def outcome_b() -> Scripts:
    return scripts_with(intake=scripted("intake", say_json(rubric_json("oos"))))


def outcome_c() -> Scripts:
    return scripts_with(
        intake=scripted("intake", say_json(POLICY)),
        retrieval=scripted("retrieval", call("search_policy", query=WEAK)),
    )


def outcome_d() -> Scripts:
    return scripts_with(
        intake=scripted("intake", say_json(ORDER)),
        order=scripted("order", call("get_order_status", order_id="NM-999999")),
    )


def outcome_e() -> Scripts:
    return scripts_with(
        intake=scripted("intake", say_json(POLICY)),
        retrieval=scripted("retrieval", call("search_policy", query=STRONG)),
        validator=scripted("validator", say_json(verdict_json((False,), 0.1))),
        composer=scripted("composer", say("Maybe.")),
    )


def outcome_answer() -> Scripts:
    return scripts_with(
        intake=scripted("intake", say_json(POLICY)),
        retrieval=scripted("retrieval", call("search_policy", query=STRONG)),
        validator=scripted("validator", say_json(verdict_json((True,), 0.95))),
        composer=scripted("composer", say("Thirty days.")),
    )


def outcome_order_answer() -> Scripts:
    return scripts_with(
        intake=scripted("intake", say_json(ORDER)),
        order=scripted("order", call("check_return_eligibility", order_id="NM-480101")),
        composer=scripted("composer", say("Eligible.")),
    )


OUTCOMES: dict[str, Callable[[], Scripts]] = {
    "A clarify": outcome_a,
    "B decline": outcome_b,
    "C no evidence": outcome_c,
    "D not found": outcome_d,
    "E low-band answer": outcome_e,
    "answer": outcome_answer,
    "order answer": outcome_order_answer,
}


def run_one(
    scripts: Scripts, data_dir: Path, tmp_path: Path, show_cost: bool
) -> tuple[World, str, dict[str, object]]:
    world = build_world(scripts, data_dir, tmp_path / "c", WorldOptions(show_cost=show_cost))
    (turn,) = world.run("A question?")
    return world, turn.reply, turn.state


@pytest.mark.parametrize("name", list(OUTCOMES))
def test_the_cost_line_is_present_on_every_outcome_with_the_flag_on(
    data_dir: Path, tmp_path: Path, name: str
) -> None:
    _, reply, _ = run_one(OUTCOMES[name](), data_dir, tmp_path, True)
    assert "\n\nCost: " in reply, name


@pytest.mark.parametrize("name", list(OUTCOMES))
def test_the_flag_hides_the_line_on_every_outcome_but_recording_stays_on(
    data_dir: Path, tmp_path: Path, name: str
) -> None:
    _, reply, state = run_one(OUTCOMES[name](), data_dir, tmp_path, False)
    assert "Cost:" not in reply, name
    session = state[STATE_SESSION_COST]
    assert isinstance(session, dict)
    assert session["questions"] == 1


def test_the_not_determinable_reply_has_the_cost_line_with_the_flag_on_and_not_off(
    data_dir: Path, tmp_path: Path
) -> None:
    documents = load_documents(data_dir / "docs")
    broken = tuple(
        replace(d, metadata={}) if d.doc_id == "returns-policy" else d for d in documents
    )
    for show in (True, False):
        scripts = scripts_with(
            intake=scripted("intake", say_json(ORDER)),
            order=scripted("order", call("check_return_eligibility", order_id="NM-480101")),
        )
        options = WorldOptions(show_cost=show, documents=broken)
        world = build_world(scripts, data_dir, tmp_path / f"c{show}", options)
        (turn,) = world.run("Can I return NM-480101?")
        assert ("Cost:" in turn.reply) is show


def test_a_precheck_decline_shows_zero_dollars_and_zero_calls(
    data_dir: Path, tmp_path: Path
) -> None:
    world = build_world(scripts_with(), data_dir, tmp_path / "c")
    ((turn),) = world.run("")
    reply, state = turn.reply, turn.state
    assert "Cost: $0.00 this answer (0 calls) | session $0.00 over 1 question" in reply
    assert state[STATE_USAGE] == []


def test_thinking_tokens_count_as_output_in_the_line(data_dir: Path, tmp_path: Path) -> None:
    """Each scripted call reports 100 prompt, 20 candidate and 30 thinking tokens."""
    _, reply, _ = run_one(outcome_answer(), data_dir, tmp_path, True)
    # intake, retrieval, validator, composer = 4 calls; one embedding estimate is not a chat call
    assert "(4 calls, 400 in / 200 out tokens)" in reply


def test_the_session_total_grows_across_questions_and_the_label_shows_once(
    data_dir: Path, tmp_path: Path
) -> None:
    oos = say_json(rubric_json("oos"))
    scripts = scripts_with(intake=scripted("intake", oos, oos))
    world = build_world(scripts, data_dir, tmp_path / "c")
    first, second = world.run("Capital of France?", "And of Spain?")
    assert "over 1 question | API-equivalent estimate, not billed" in first.reply
    assert "over 2 questions" in second.reply
    assert "not billed" not in second.reply
    cost = second.state[STATE_SESSION_COST]
    assert isinstance(cost, dict)
    assert cost["questions"] == 2
    assert cost["usd"] == pytest.approx(2 * (100 * 1.0 + 50 * 2.0) / 1_000_000)


def test_the_embedding_estimate_adds_to_the_price_but_not_to_the_call_count(
    data_dir: Path, tmp_path: Path
) -> None:
    _, reply, state = run_one(outcome_c(), data_dir, tmp_path, True)
    records = state[STATE_USAGE]
    assert isinstance(records, list)
    assert [r["kind"] for r in records] == ["chat", "chat", "embedding"]
    assert "(2 calls," in reply
