"""ADK evalsets for tool trajectories (task 8.4, design D7). Key-free: the generated files are
checked against the case files and parsed by ADK's own models; `adk eval` itself is not run."""

import json
from pathlib import Path

from google.adk.evaluation.eval_config import EvalConfig
from google.adk.evaluation.eval_metrics import ToolTrajectoryCriterion
from google.adk.evaluation.eval_set import EvalSet

from evalkit import adk_commands, evalset_files, load_all_cases

EVALS = Path(__file__).resolve().parent.parent / "evals"
CASES = load_all_cases(EVALS / "cases")


def test_the_evalset_files_on_disk_match_what_the_case_files_generate() -> None:
    expected = evalset_files(CASES)
    on_disk = {
        p.relative_to(EVALS / "evalsets").as_posix(): p.read_text(encoding="utf-8")
        for p in (EVALS / "evalsets").rglob("*.json")
    }
    assert on_disk == expected, "run: python backend/evals/build_evalsets.py"


def test_every_generated_evalset_parses_as_an_adk_evalset_with_its_expected_tools() -> None:
    sets = [f for f in evalset_files(CASES).items() if f[0].endswith(".evalset.json")]
    assert sets
    for name, text in sets:
        evalset = EvalSet.model_validate_json(text)
        for case in evalset.eval_cases:
            assert case.conversation is not None and case.session_input is not None
            assert case.session_input.state == {}  # persona comes from NOVAMART_USER, not state
            (invocation,) = case.conversation
            tools = [u.name for u in invocation.intermediate_data.tool_uses]  # type: ignore[union-attr]
            assert ("exact/" in name) == (tools == []), name


def test_each_config_uses_the_trajectory_metric_alone_with_names_only() -> None:
    for group, match in (("in_order", "IN_ORDER"), ("exact", "EXACT")):
        raw = (EVALS / "evalsets" / group / "test_config.json").read_text(encoding="utf-8")
        config = EvalConfig.model_validate_json(raw)
        assert list(config.criteria) == ["tool_trajectory_avg_score"]  # no ROUGE response match
        criterion = ToolTrajectoryCriterion.model_validate(
            config.criteria["tool_trajectory_avg_score"].model_dump()  # type: ignore[union-attr]
        )
        assert criterion.match_type.name == match and criterion.ignore_args is True
        assert json.loads(raw)["criteria"]["tool_trajectory_avg_score"]["threshold"] == 1.0


def test_cases_that_adk_cannot_score_are_left_to_the_custom_runner() -> None:
    exported = {
        c["eval_id"]
        for name, text in evalset_files(CASES).items()
        if name.endswith(".evalset.json")
        for c in json.loads(text)["eval_cases"]
    }
    multi_turn = {c.case_id for c in CASES if len(c.turns) > 1}
    fixture = {c.case_id for c in CASES if c.fixture}
    assert not (exported & (multi_turn | fixture))
    assert "unknown-order-not-found" not in exported  # pins no tool: not a trajectory case


def test_adk_commands_set_one_persona_per_evalset_and_pass_the_group_config() -> None:
    commands = adk_commands(EVALS / "evalsets", Path("agent_dir"), None)
    assert commands
    for command in commands:
        assert command.argv[:2] == ("adk", "eval")
        assert command.persona in command.argv[3]
        flags = [a for a in command.argv if a.startswith("--config_file_path=")]
        assert flags and "test_config.json" in flags[0]
    only = adk_commands(EVALS / "evalsets", Path("agent_dir"), "security")
    assert only and all("security." in c.argv[3] for c in only)
