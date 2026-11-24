"""The shipped case files, loaded together (quality then security)."""

from pathlib import Path

from evalkit.cases import Case, load_cases
from evalkit.errors import CaseError

CASE_FILES = ("quality.json", "security.json")


def load_all_cases(cases_dir: Path) -> tuple[Case, ...]:
    """Quality then security cases; ids are unique across both files."""
    cases = tuple(c for name in CASE_FILES for c in load_cases(cases_dir / name))
    ids = [c.case_id for c in cases]
    if len(set(ids)) != len(ids):
        raise CaseError("case ids must be unique across the quality and security files")
    return cases
