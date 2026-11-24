"""Traceability (task 8.1): 'Traceability map'. Every spec scenario of the change maps to an eval
case id, or to a named test or document with a reason; every mapped id exists; every case's
scenario is mapped back to it. Key-free: reads the specs and the case files."""

import json
import re
from pathlib import Path

import pytest

from evalkit import load_all_cases

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "backend" / "evals"
SPECS = ROOT / "openspec" / "changes" / "novamart-rag-agent" / "specs"
MAP = json.loads((EVALS / "cases" / "traceability.json").read_text(encoding="utf-8"))["scenarios"]
CASE_IDS = {c.case_id for c in load_all_cases(EVALS / "cases")}
SCENARIO = re.compile(r"^#### Scenario: (.+)$", re.MULTILINE)

pytestmark = pytest.mark.skipif(not SPECS.is_dir(), reason="change specs archived or moved")


def spec_scenarios() -> set[str]:
    keys: set[str] = set()
    for spec in SPECS.glob("*/spec.md"):
        for title in SCENARIO.findall(spec.read_text(encoding="utf-8")):
            keys.add(f"{spec.parent.name}/{title.strip()}")
    return keys


def test_every_spec_scenario_is_in_the_traceability_map() -> None:
    assert spec_scenarios() - set(MAP) == set()


def test_the_map_names_no_scenario_the_specs_do_not_have() -> None:
    assert set(MAP) - spec_scenarios() == set()


def test_every_mapped_case_id_exists() -> None:
    for scenario, entry in MAP.items():
        for case_id in entry.get("cases", []):
            assert case_id in CASE_IDS, f"{scenario}: unknown case {case_id}"


def test_a_scenario_without_a_case_names_the_test_or_document_and_a_reason() -> None:
    for scenario, entry in MAP.items():
        assert bool(entry.get("cases")) != bool(entry.get("covered_by")), scenario
        if "covered_by" in entry:
            path, _, reason = entry["covered_by"].partition(" :: ")
            assert (ROOT / path).exists(), f"{scenario}: {path} does not exist"
            assert reason.strip(), f"{scenario}: no reason given"


def test_every_scenario_about_behavior_has_an_eval_case_not_only_a_test() -> None:
    behavior = ("policy-retrieval/", "order-tools/", "access-control/")
    for scenario, entry in MAP.items():
        if scenario.startswith(behavior) and "covered_by" in entry:
            assert scenario in {
                "access-control/Tools take no identity parameters",
                "access-control/Repository secret scan",
                "order-tools/Policy cannot be determined",
                "policy-retrieval/Uncovered required criterion caps the band",
            }, f"{scenario} needs an eval case (ARCH-TEST-3)"


def test_every_case_proves_a_scenario_the_map_lists_it_under() -> None:
    mapped = {c for entry in MAP.values() for c in entry.get("cases", [])}
    assert CASE_IDS <= mapped, f"cases not mapped to any scenario: {sorted(CASE_IDS - mapped)}"
    by_id = {c.case_id: c for c in load_all_cases(EVALS / "cases")}
    for case_id, case in by_id.items():
        listed = [k for k, v in MAP.items() if case_id in v.get("cases", [])]
        assert any(k.endswith("/" + case.scenario) for k in listed), case_id
