"""Eval kit reporting (task 8.4): 'Run and report', 'Failures present', 'Cost recorded per case'.
Key-free: cases are graded over hand-built observations."""

import json
from pathlib import Path

from evalkit import (
    Case,
    SeededValue,
    failed_run,
    grade_case,
    load_all_cases,
    pass_rate,
    select_cases,
    summarize,
    write_results,
)
from evalkit.cases import CheckSpec
from evalkit.grade import redact
from evalkit.render import render_json, render_markdown
from evals_support import NOT_FOUND, obs, turn, unpriced

EVALS = Path(__file__).resolve().parent.parent / "evals"
LEAK = SeededValue("NM-1.email", "ann@example.test")


def make_case(case_id: str, qtype: str, *checks: CheckSpec) -> Case:
    return Case(case_id, "quality", "Scenario", qtype, "emp_store7", ("q",), "e", checks)


def spec(kind: str, **args: object) -> CheckSpec:
    return CheckSpec(kind, args)


def graded() -> tuple[list, object]:  # type: ignore[type-arg]
    unknown = make_case("unknown-order", "refusal", spec("reply_equals_canned", name="not_found"))
    leak = make_case("leaky", "order", spec("customer_data_absent"))
    ok = grade_case(unknown, obs(turn(NOT_FOUND, kind="not_found", agents=("intake", "order"))))
    bad = grade_case(leak, obs(turn("mail ann@example.test", agents=("intake",)), seeded=(LEAK,)))
    results = [ok, bad, failed_run(make_case("broken", "policy", spec("no_tools")), "ClientError")]
    return results, summarize("quality", results)


def test_a_case_passes_only_when_every_check_passes() -> None:
    case = make_case("c", "policy", spec("no_tools"), spec("tool_called", tool="search_policy"))
    result = grade_case(case, obs(turn("x")))
    assert not result.passed
    assert [c.passed for c in result.checks] == [True, False]


def test_per_case_results_and_an_overall_pass_rate_are_produced() -> None:
    results, summary = graded()
    assert [r.passed for r in results] == [True, False, False]
    assert summary.total == 3 and summary.passed == 1
    assert abs(summary.pass_rate - 1 / 3) < 1e-9
    assert pass_rate([]) == 0.0


def test_every_failing_case_is_listed_with_its_cause_none_omitted() -> None:
    results, summary = graded()
    markdown = render_markdown(results, summary)
    failures = markdown.split("## Failures")[1]
    assert "leaky" in failures and "customer_data_absent" in failures
    assert "broken" in failures and "run failed: ClientError" in failures
    assert "unknown-order" not in failures
    assert len(summary.failures) == 2


def test_the_summary_reports_calls_and_cost_per_question_and_at_1000_questions() -> None:
    results, summary = graded()
    assert summary.mean_calls == 1.5  # (2 + 1) calls over the two questions that ran
    assert summary.mean_usd is not None and abs(summary.mean_usd - 0.001) < 1e-12
    assert summary.usd_at_1000 is not None and abs(summary.usd_at_1000 - 1.0) < 1e-9
    markdown = render_markdown(results, summary)
    assert "cost at 1,000 questions: $1.0000" in markdown and "## By question type" in markdown


def test_an_unpriced_question_makes_the_mean_unavailable_never_zero() -> None:
    case = make_case("c", "policy", spec("no_tools"))
    summary = summarize("quality", [grade_case(case, obs(unpriced(turn("x"))))])
    assert summary.mean_usd is None and summary.usd_at_1000 is None
    assert "cost unavailable" in render_markdown([], summary)


def test_results_hold_per_question_figures_and_the_redacted_reply_but_no_customer_data() -> None:
    results, summary = graded()
    data = json.loads(render_json(results, summary))
    first = data["cases"][0]["turns"][0]
    assert first["model_calls"] == 2 and first["usd"] == 0.001 and first["outcome"] == "D"
    assert first["input_tokens"] == 200 and first["output_tokens"] == 100
    assert first["message"] == "q" and first["reply"].startswith(NOT_FOUND)
    leaky = data["cases"][1]["turns"][0]
    assert leaky["reply"] == "mail [redacted:NM-1.email]"
    blob = render_json(results, summary) + render_markdown(results, summary)
    assert "ann@example.test" not in blob


def test_a_failing_case_shows_its_question_and_reply_in_the_markdown() -> None:
    results, summary = graded()
    failures = render_markdown(results, summary).split("## Failures")[1]
    assert "question 1: q" in failures and "> mail [redacted:NM-1.email]" in failures
    assert NOT_FOUND not in failures  # a passing case's reply is not repeated


def test_redaction_ignores_letter_case_and_prefers_the_longest_value() -> None:
    short = SeededValue("NM-2.name", "Ann")
    long = SeededValue("NM-2.address", "Ann Lee, 5 Main St")
    assert redact("ANN LEE, 5 MAIN ST and ann", (short, long)) == (
        "[redacted:NM-2.address] and [redacted:NM-2.name]"
    )


def test_results_are_written_as_markdown_and_json_files(tmp_path: Path) -> None:
    results, summary = graded()
    markdown, data = write_results(tmp_path / "results", "20261124-120000", results, summary)
    assert markdown.name == "quality-20261124-120000.md" and markdown.read_text()
    assert json.loads(data.read_text())["pass_rate"] == summary.pass_rate


def test_the_shipped_sets_group_into_per_type_figures() -> None:
    cases = select_cases(load_all_cases(EVALS / "cases"), "quality", ())
    results = [failed_run(c, "NotRun") for c in cases]
    summary = summarize("quality", results)
    assert {g.name for g in summary.groups} == {"policy", "product", "order", "combined", "refusal"}
    assert summary.total == len(cases) and summary.passed == 0
