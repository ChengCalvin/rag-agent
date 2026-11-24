"""Case files: typed models parsed once at load (TYPE-2). A bad file fails here, not mid-run."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from evalkit.checks import REGISTRY
from evalkit.errors import CaseError

QUESTION_TYPES = frozenset({"policy", "product", "order", "combined", "refusal"})
SETS = frozenset({"quality", "security"})
OUTCOMES = frozenset({"A", "B", "C", "D", "E"})
_ID = re.compile(r"[a-z0-9][a-z0-9-]*")

# Arguments each check kind needs, so a typo fails at load.
_REQUIRED: Mapping[str, tuple[str, ...]] = {
    "reply_contains_any": ("values",),
    "reply_contains_all": ("values",),
    "reply_not_contains": ("values",),
    "reply_matches": ("pattern",),
    "reply_not_matches": ("pattern",),
    "reply_equals_canned": ("name",),
    "every_reply_equals_canned": ("name",),
    "cites": ("file",),
    "band_is": ("band",),
    "tool_called": ("tool",),
    "tool_not_called": ("tool",),
    "agent_not_called": ("agent",),
    "log_contains": ("text",),
    "outcome_is": ("outcome",),
    "outcome_not": ("outcome",),
    "model_calls_equal": ("count",),
}


@dataclass(frozen=True)
class CheckSpec:
    """One check as written in the case file."""

    kind: str
    args: Mapping[str, object]


@dataclass(frozen=True)
class Case:
    """One eval case. `scenario` is the spec scenario title it proves (ARCH-TEST-2)."""

    case_id: str
    set_name: str
    scenario: str
    question_type: str
    persona: str
    turns: tuple[str, ...]
    expected: str
    checks: tuple[CheckSpec, ...]
    refusal_outcome: str | None = None
    known_limitation: bool = False
    fixture: str | None = None

    def adk_expected_tools(self) -> tuple[str, ...] | None:
        """Tool names the case requires (for the ADK trajectory), or None when not pinned."""
        called = [str(c.args["tool"]) for c in self.checks if c.kind == "tool_called"]
        if called:
            return tuple(called)
        if any(c.kind == "no_tools" for c in self.checks):
            return ()
        return None


def _str(raw: Mapping[str, object], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CaseError(f"{where}: '{key}' must be a non-empty string")
    return value


def _check(raw: object, where: str) -> CheckSpec:
    if not isinstance(raw, dict):
        raise CaseError(f"{where}: a check must be an object")
    kind = _str(raw, "kind", where)
    if kind not in REGISTRY:
        raise CaseError(f"{where}: unknown check kind '{kind}'")
    args = {k: v for k, v in raw.items() if k != "kind"}
    missing = [k for k in _REQUIRED.get(kind, ()) if k not in args]
    if missing:
        raise CaseError(f"{where}: check '{kind}' lacks {missing}")
    return CheckSpec(kind, args)


def _turns(raw: Mapping[str, object], where: str) -> tuple[str, ...]:
    turns = raw.get("turns")
    ok = isinstance(turns, list) and turns and all(isinstance(t, str) and t for t in turns)
    if not ok:
        raise CaseError(f"{where}: 'turns' must be a non-empty list of messages")
    assert isinstance(turns, list)
    return tuple(str(t) for t in turns)


def parse_case(raw: object, index: int) -> Case:
    if not isinstance(raw, dict):
        raise CaseError(f"case {index}: must be an object")
    case_id = _str(raw, "id", f"case {index}")
    where = f"case '{case_id}'"
    if not _ID.fullmatch(case_id):
        raise CaseError(f"{where}: id must be lowercase letters, digits and hyphens")
    set_name, qtype = _str(raw, "set", where), _str(raw, "type", where)
    outcome = raw.get("refusal_outcome")
    if set_name not in SETS or qtype not in QUESTION_TYPES:
        raise CaseError(f"{where}: unknown set or type")
    if outcome is not None and outcome not in OUTCOMES:
        raise CaseError(f"{where}: refusal_outcome must be one of A to E")
    checks = raw.get("checks")
    if not isinstance(checks, list) or not checks:
        raise CaseError(f"{where}: needs at least one check")
    fixture = raw.get("fixture")
    return Case(
        case_id=case_id,
        set_name=set_name,
        scenario=_str(raw, "scenario", where),
        question_type=qtype,
        persona=_str(raw, "persona", where),
        turns=_turns(raw, where),
        expected=_str(raw, "expected", where),
        checks=tuple(_check(c, where) for c in checks),
        refusal_outcome=outcome if isinstance(outcome, str) else None,
        known_limitation=raw.get("known_limitation") is True,
        fixture=fixture if isinstance(fixture, str) else None,
    )


def load_cases(path: Path) -> tuple[Case, ...]:
    """Load one case file; ids must be unique within it."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise CaseError(f"{path.name}: not valid JSON") from None
    raw_cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(raw_cases, list):
        raise CaseError(f"{path.name}: needs a 'cases' list")
    cases = tuple(parse_case(raw, i) for i, raw in enumerate(raw_cases))
    ids = [c.case_id for c in cases]
    if len(set(ids)) != len(ids):
        raise CaseError(f"{path.name}: duplicate case id")
    return cases


def select_cases(
    cases: tuple[Case, ...], set_name: str | None, only_ids: tuple[str, ...]
) -> tuple[Case, ...]:
    """The cases to run: one set (or all) and, when given, only the named ids (all must exist)."""
    known = {c.case_id for c in cases}
    unknown = [i for i in only_ids if i not in known]
    if unknown:
        raise CaseError(f"unknown case id: {unknown}")
    chosen = tuple(c for c in cases if set_name in (None, c.set_name))
    return tuple(c for c in chosen if not only_ids or c.case_id in only_ids)
