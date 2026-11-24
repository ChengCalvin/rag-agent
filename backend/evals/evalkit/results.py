"""Result types shared by checks and the report (pure)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome. `detail` says why it failed and never holds personal data."""

    kind: str
    passed: bool
    detail: str = ""


def verdict(kind: str, passed: bool, failure_detail: str) -> CheckResult:
    """A result whose detail is only kept when the check failed."""
    return CheckResult(kind, passed, "" if passed else failure_detail)
