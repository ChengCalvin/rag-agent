"""Eval driver turn logic (task 8.4) against the REAL orchestrator with scripted models: the
shipped eval cases are graded over what `run_turn` reads from a real graph run, so the checks,
the outcome letters and the cost figures are proven to agree with the pipeline. No key, no
network: the models are `ScriptedLlm`, the embeddings are fake."""

import asyncio
from pathlib import Path

from google.adk.runners import Runner

from evalkit import Case, Observation, TurnObservation, grade_case, load_all_cases, outcome_of
from evalkit.drive import LiveSession, run_turn
from evalkit.seeded import load_seeded_values
from stub_llm import call, say, say_json, scripted
from world import APP, Scripts, World, WorldOptions, build_world, rubric_json, unused, verdict_json

EVALS = Path(__file__).resolve().parent.parent / "evals"
CASES = {c.case_id: c for c in load_all_cases(EVALS / "cases")}
ORDER = rubric_json("order", (("order", True),))
POLICY = rubric_json("knowledge", (("window", True),), doc_type="policy")
STRONG, WEAK = "returns refund window days policy", "xylophone zebra"


def scripts(**models: object) -> Scripts:
    base = {n: unused(n) for n in ("intake", "retrieval", "validator", "order", "composer")}
    return Scripts(**{**base, **models})  # type: ignore[arg-type]


def run_turns(world: World, *messages: str) -> list[TurnObservation]:
    async def go() -> list[TurnObservation]:
        await world.service.create_session(app_name=APP, user_id="u", session_id="s", state={})
        runner = Runner(node=world.workflow, app_name=APP, session_service=world.service)
        live = LiveSession(runner, world.service, APP, "u", "s")
        return [await run_turn(live, m, world.settings.prices) for m in messages]

    return asyncio.run(go())


def grade(case: Case, turns: list[TurnObservation], data_dir: Path) -> list[str]:
    seeded = load_seeded_values(data_dir / "orders.json")
    result = grade_case(case, Observation(tuple(turns), "", seeded))
    return [f"{c.kind}: {c.detail}" for c in result.checks if not c.passed]


def test_outcome_a_clarification_passes_its_shipped_case(data_dir: Path, tmp_path: Path) -> None:
    rubric = rubric_json("clarify", (("which order", True),), slots=("order_number",))
    world = build_world(scripts(intake=scripted("intake", say_json(rubric))), data_dir, tmp_path)
    case = CASES["order-number-missing-asks-one-question"]
    turns = run_turns(world, *case.turns)
    assert outcome_of(turns[0]) == "A"
    assert grade(case, turns, data_dir) == []


def test_outcome_b_decline_passes_its_shipped_case(data_dir: Path, tmp_path: Path) -> None:
    oos = scripted("intake", say_json(rubric_json("oos")))
    world = build_world(scripts(intake=oos), data_dir, tmp_path)
    case = CASES["out-of-domain-question-declined"]
    assert grade(case, run_turns(world, *case.turns), data_dir) == []


def test_outcome_c_no_evidence_passes_its_shipped_case(data_dir: Path, tmp_path: Path) -> None:
    model = scripts(
        intake=scripted("intake", say_json(POLICY)),
        retrieval=scripted("retrieval", call("search_policy", query=WEAK)),
    )
    case = CASES["question-below-the-cosine-threshold-dress-code"]
    turns = run_turns(build_world(model, data_dir, tmp_path), *case.turns)
    assert outcome_of(turns[0]) == "C"
    assert grade(case, turns, data_dir) == []


def test_outcome_d_unknown_order_passes_its_shipped_case(data_dir: Path, tmp_path: Path) -> None:
    model = scripts(
        intake=scripted("intake", say_json(ORDER)),
        order=scripted("order", call("get_order_status", order_id="NM-999999")),
    )
    case = CASES["unknown-order-not-found"]
    turns = run_turns(build_world(model, data_dir, tmp_path), *case.turns)
    assert [c.name for c in turns[0].tool_calls] == ["get_order_status"]
    assert grade(case, turns, data_dir) == []


def test_outcome_e_is_a_low_band_answer_not_a_refusal(data_dir: Path, tmp_path: Path) -> None:
    model = scripts(
        intake=scripted("intake", say_json(POLICY)),
        retrieval=scripted("retrieval", call("search_policy", query=STRONG)),
        validator=scripted("validator", say_json(verdict_json((False,), 0.1))),
        composer=scripted("composer", say("Maybe.")),
    )
    (turn,) = run_turns(build_world(model, data_dir, tmp_path), "A question?")
    assert outcome_of(turn) == "E" and turn.final_kind == "knowledge_answer"
    assert turn.cost.calls == 4 and turn.cost.usd is not None and turn.cost.usd > 0


def test_a_precheck_decline_costs_nothing_and_passes_the_role_claim_case(
    data_dir: Path, tmp_path: Path
) -> None:
    world = build_world(scripts(), data_dir, tmp_path, WorldOptions(user="emp_store12"))
    case = CASES["role-claimed-in-chat-caught-by-precheck"]
    turns = run_turns(world, *case.turns)
    assert turns[0].cost.calls == 0 and turns[0].cost.usd == 0.0
    assert grade(case, turns, data_dir) == []


def test_cross_store_and_nonexistent_orders_pass_the_denial_parity_case(
    data_dir: Path, tmp_path: Path
) -> None:
    model = scripts(
        intake=scripted("intake", say_json(ORDER), say_json(ORDER)),
        order=scripted(
            "order",
            call("get_order_status", order_id="NM-480101"),
            call("get_order_status", order_id="NM-999999"),
        ),
    )
    world = build_world(model, data_dir, tmp_path, WorldOptions(user="emp_store12"))
    case = CASES["cross-store-request"]
    turns = run_turns(world, *case.turns)
    assert grade(case, turns, data_dir) == []
    assert turns[0].cost.calls == turns[1].cost.calls == 2


def test_a_permitted_lookup_is_labelled_from_order_records_with_no_band(
    data_dir: Path, tmp_path: Path
) -> None:
    model = scripts(
        intake=scripted("intake", say_json(ORDER)),
        order=scripted("order", call("get_order_status", order_id="NM-480103")),
        composer=scripted("composer", say("The NovaCool fridge is in transit, due 2026-11-26.")),
    )
    case = CASES["permitted-order-status-and-order-shortcut"]
    turns = run_turns(build_world(model, data_dir, tmp_path), *case.turns)
    assert grade(case, turns, data_dir) == []
