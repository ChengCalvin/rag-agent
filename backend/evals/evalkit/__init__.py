"""Eval kit: typed cases, objective checks, grading, reporting and the live driver.

Public names are exposed here. Everything except `drive` (and the CLI that calls it) is pure and
key-free, and is tested with fakes under `backend/tests/`.
"""

from evalkit.adk_evalset import evalset_files
from evalkit.adk_step import AdkCommand, adk_commands, adk_record
from evalkit.case_set import CASE_FILES, load_all_cases
from evalkit.cases import Case, CheckSpec, load_cases, select_cases
from evalkit.checks import REGISTRY, run_check
from evalkit.errors import CaseError
from evalkit.grade import CaseResult, TurnMetrics, failed_run, grade_case
from evalkit.observation import (
    Observation,
    SeededValue,
    ToolCall,
    TurnObservation,
    outcome_of,
    strip_cost_line,
)
from evalkit.results import CheckResult
from evalkit.summary import Summary, pass_rate, summarize
from evalkit.write_results import write_results

__all__: list[str] = [
    "CASE_FILES",
    "REGISTRY",
    "AdkCommand",
    "Case",
    "CaseError",
    "CaseResult",
    "CheckResult",
    "CheckSpec",
    "Observation",
    "SeededValue",
    "Summary",
    "ToolCall",
    "TurnMetrics",
    "TurnObservation",
    "adk_commands",
    "adk_record",
    "evalset_files",
    "failed_run",
    "grade_case",
    "load_all_cases",
    "load_cases",
    "outcome_of",
    "pass_rate",
    "run_check",
    "select_cases",
    "strip_cost_line",
    "summarize",
    "write_results",
]
