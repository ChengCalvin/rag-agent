"""Eval cases (tasks 8.2, 8.3): 'Coverage of question types', 'Coverage of refusal outcomes',
'Combined question known limitation', and that each case's expectations agree with the shipped
documents, canned wording and precheck, so a case cannot be unfair or vacuous.
Key-free: reads the case files and the synthetic data only."""

import json
from collections import Counter
from pathlib import Path

import pytest

from evalkit import Case, CaseError, load_all_cases, load_cases, select_cases
from novamart_agent.config import PipelineSettings
from novamart_agent.pipeline import precheck
from novamart_agent.prompts import (
    LOW_CONFIDENCE_NOTE,
    ORDER_LIMITATION_SENTENCE,
    ORDER_RECORDS_LABEL,
    clarification_reply,
)
from novamart_agent.rag import escalation_contact, load_documents
from novamart_agent.security import load_principals

EVALS = Path(__file__).resolve().parent.parent / "evals"
DATA = Path(__file__).resolve().parent.parent / "data"
CASES = load_all_cases(EVALS / "cases")
QUALITY = [c for c in CASES if c.set_name == "quality"]
SECURITY = [c for c in CASES if c.set_name == "security"]
BY_ID = {c.case_id: c for c in CASES}


def test_the_quality_set_has_15_to_18_cases() -> None:
    assert 15 <= len(QUALITY) <= 18


def test_coverage_of_question_types_has_at_least_two_cases_of_each() -> None:
    counts = Counter(c.question_type for c in QUALITY)
    answerable = counts["policy"] + counts["product"]
    assert answerable >= 2 and counts["order"] >= 2
    assert counts["combined"] >= 2 and counts["refusal"] >= 2


def test_coverage_of_refusal_outcomes_is_exactly_a_to_e_once_each() -> None:
    outcomes = sorted(c.refusal_outcome for c in QUALITY if c.refusal_outcome)
    assert outcomes == ["A", "B", "C", "D", "E"]
    for case in QUALITY:
        if case.refusal_outcome:
            wanted = [c for c in case.checks if c.kind == "outcome_is"]
            assert wanted[0].args["outcome"] == case.refusal_outcome


def test_combined_question_known_limitation_cases_are_labelled_and_check_the_limitation() -> None:
    combined = [c for c in QUALITY if c.question_type == "combined"]
    assert combined and all(c.known_limitation for c in combined)
    for case in combined:
        said = [c.args["values"] for c in case.checks if c.kind == "reply_contains_all"]
        assert ["cannot answer the policy part"] in said
        no_search = [c for c in case.checks if c.kind == "tool_not_called"]
        assert any(c.args["tool"] == "search_policy" for c in no_search)
    assert not any(c.known_limitation for c in CASES if c.question_type != "combined")


def test_the_limitation_check_text_is_in_the_real_limitation_sentence() -> None:
    assert "cannot answer the policy part" in ORDER_LIMITATION_SENTENCE


def test_every_case_states_persona_expected_behavior_and_checks() -> None:
    personas = set(load_principals(DATA / "users.json"))
    for case in CASES:
        assert case.persona in personas, case.case_id
        assert case.expected and case.checks and case.turns


def test_security_set_covers_every_required_category() -> None:
    ids = {c.case_id for c in SECURITY}
    required = {
        "cross-store-request",
        "role-claimed-in-chat-caught-by-precheck",
        "role-claimed-in-chat-passes-precheck",
        "poisoned-document",
        "rubric-or-rewrite-injection",
        "log-contains-no-customer-data",
        "employee-asks-about-manager-only-content",
        "denial-indistinguishable-from-not-found",
    }
    assert required <= ids


def test_every_security_case_has_a_pass_condition_in_its_expected_text() -> None:
    for case in SECURITY:
        assert case.expected.startswith(("Pass only if", "Positive control")), case.case_id


def test_cited_files_exist_in_the_documents_or_the_fixtures() -> None:
    names = {p.name for p in (DATA / "docs").glob("*.md")}
    names |= {p.name for p in (EVALS / "fixtures").glob("*/*.md")}
    for case in CASES:
        for check in case.checks:
            if check.kind == "cites":
                assert check.args["file"] in names, case.case_id


def test_fixture_cases_name_an_existing_fixture_directory() -> None:
    for case in CASES:
        if case.fixture:
            assert (EVALS / "fixtures" / case.fixture).is_dir()


def test_the_poisoned_fixture_is_a_loadable_document_with_the_injected_instruction() -> None:
    docs = load_documents(EVALS / "fixtures" / "poisoned-courier-memo")
    (memo,) = docs
    assert memo.doc_id == "poisoned-courier-memo" and memo.audience == "all_staff"
    assert "ignore all previous rules" in memo.body.lower()


@pytest.mark.parametrize(
    ("file", "needles"),
    [
        ("product-novacool-fridge.md", ["+--------------+", "|  NovaCool    |", "15 cm"]),
        ("product-novahub-speaker.md", ["[ Home router ]", "10 metres"]),
        ("manager-approvals.md", ["15 percent", "goodwill", "reason code"]),
        ("product-novabook-launch-briefing.md", ["Wave 1", "Wave 2", "launch day"]),
        ("returns-policy.md", ["14 days"]),
        ("price-matching-policy.md", ["7 days"]),
    ],
)
def test_expected_and_forbidden_values_really_appear_in_the_documents(
    file: str, needles: list[str]
) -> None:
    text = (DATA / "docs" / file).read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{file} lacks {needle}"


def test_canned_wording_the_cases_rely_on_exists() -> None:
    contact = escalation_contact(load_documents(DATA / "docs"))
    assert "555-0142" in contact
    assert "may not fully cover" in LOW_CONFIDENCE_NOTE
    assert "From order records" in ORDER_RECORDS_LABEL
    ask = clarification_reply(["order_number"])
    assert "order number" in ask and ask.count("?") == 1


def test_precheck_behaves_as_the_security_cases_assume() -> None:
    settings = PipelineSettings()
    declines = BY_ID["role-claimed-in-chat-caught-by-precheck"].turns[0]
    assert not precheck(declines, settings).proceed
    for case_id in (
        "role-claimed-in-chat-passes-precheck",
        "rubric-or-rewrite-injection",
        "denial-indistinguishable-from-not-found",
        "request-to-change-an-order",
        "poisoned-document",
    ):
        for message in BY_ID[case_id].turns:
            assert precheck(message, settings).proceed, (case_id, message)


def test_no_quality_message_is_stopped_by_the_precheck() -> None:
    settings = PipelineSettings()
    for case in QUALITY:
        for message in case.turns:
            assert precheck(message, settings).proceed, case.case_id


def test_sequential_probing_exceeds_the_throttle_limit() -> None:
    from novamart_agent.config import DEFAULT_DENIED_LOOKUP_LIMIT

    assert len(BY_ID["sequential-identifier-probing"].turns) > DEFAULT_DENIED_LOOKUP_LIMIT


def _write(tmp_path: Path, record: object) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _valid(**changes: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "a-case", "set": "quality", "type": "policy", "persona": "emp_store7",
        "scenario": "S", "turns": ["q"], "expected": "e",
        "checks": [{"kind": "no_tools"}],
    }  # fmt: skip
    return {**case, **changes}


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "Bad Id"},
        {"set": "other"},
        {"type": "weird"},
        {"turns": []},
        {"checks": []},
        {"checks": [{"kind": "nope"}]},
        {"checks": [{"kind": "tool_called"}]},
        {"refusal_outcome": "F"},
        {"expected": ""},
    ],
)
def test_a_malformed_case_fails_at_load_not_mid_run(tmp_path: Path, bad: dict[str, object]) -> None:
    with pytest.raises(CaseError):
        load_cases(_write(tmp_path, {"cases": [_valid(**bad)]}))


def test_duplicate_ids_and_bad_files_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(CaseError):
        load_cases(_write(tmp_path, {"cases": [_valid(), _valid()]}))
    with pytest.raises(CaseError):
        load_cases(_write(tmp_path, ["not", "an", "object"]))
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(CaseError):
        load_cases(broken)


def test_select_cases_filters_by_set_and_id_and_rejects_unknown_ids() -> None:
    assert {c.set_name for c in select_cases(CASES, "security", ())} == {"security"}
    (one,) = select_cases(CASES, None, ("unknown-order-not-found",))
    assert isinstance(one, Case) and one.case_id == "unknown-order-not-found"
    with pytest.raises(CaseError):
        select_cases(CASES, None, ("no-such-case",))
