"""Render a summary as Markdown and JSON (pure; the files are written by `write_results`)."""

import json
from collections.abc import Sequence
from dataclasses import asdict

from evalkit.grade import CaseResult
from evalkit.summary import Summary


def _usd(value: float | None) -> str:
    return "cost unavailable" if value is None else f"${value:.4f}"


def _failure_lines(result: CaseResult) -> list[str]:
    head = f"- `{result.case_id}` ({result.scenario})"
    if result.error:
        return [f"{head}: run failed: {result.error}"]
    lines = [head, *(f"  - {c.kind}: {c.detail}" for c in result.checks if not c.passed)]
    for number, turn in enumerate(result.turns, start=1):
        lines.append(f"  - question {number}: {turn.message}")
        reply_rows = (turn.reply or "(no reply)").split("\n")
        lines.extend(f"    > {row}" for row in reply_rows)
    return lines


def render_markdown(results: Sequence[CaseResult], summary: Summary) -> str:
    """Per-case table, per-type figures and every failure with the checks that failed."""
    rate = f"{summary.pass_rate:.0%}"
    lines = [
        f"# {summary.name} evaluation results",
        "",
        f"Overall pass rate: {summary.passed}/{summary.total} ({rate})",
        f"Mean model calls per question: {summary.mean_calls:.2f}; "
        f"mean cost per question: {_usd(summary.mean_usd)}; "
        f"cost at 1,000 questions: {_usd(summary.usd_at_1000)} (API-equivalent, not billed)",
        "",
        "| case | type | result | questions | model calls | cost |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        calls = sum(t.model_calls for t in r.turns)
        usd = None if any(t.usd is None for t in r.turns) else sum(t.usd or 0 for t in r.turns)
        label = "PASS" if r.passed else "FAIL"
        known = " (known limitation)" if r.known_limitation else ""
        lines.append(
            f"| {r.case_id}{known} | {r.question_type} | {label} | {len(r.turns)} | {calls} "
            f"| {_usd(usd) if r.turns else 'n/a'} |"
        )
    lines += ["", "## By question type", ""]
    lines += ["| type | passed | mean calls | mean cost |", "|---|---|---|---|"]
    lines += [
        f"| {g.name} | {g.passed}/{g.cases} | {g.mean_calls:.2f} | {_usd(g.mean_usd)} |"
        for g in summary.groups
    ]
    lines += ["", "## Failures", ""]
    if not summary.failures:
        lines.append("None.")
    for failure in summary.failures:
        lines += _failure_lines(failure)
    return "\n".join(lines) + "\n"


def render_json(results: Sequence[CaseResult], summary: Summary) -> str:
    """The same figures as data. No reply text is stored (ERR-2)."""
    record = {
        "set": summary.name,
        "pass_rate": summary.pass_rate,
        "passed": summary.passed,
        "total": summary.total,
        "mean_calls": summary.mean_calls,
        "mean_usd": summary.mean_usd,
        "usd_at_1000": summary.usd_at_1000,
        "cases": [asdict(r) for r in results],
    }
    return json.dumps(record, indent=2, sort_keys=True) + "\n"
