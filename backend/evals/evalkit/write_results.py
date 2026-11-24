"""Write a run's files to `backend/evals/results/` (the only file I/O of reporting)."""

from collections.abc import Sequence
from pathlib import Path

from evalkit.grade import CaseResult
from evalkit.render import render_json, render_markdown
from evalkit.summary import Summary


def write_results(
    out_dir: Path, stamp: str, results: Sequence[CaseResult], summary: Summary
) -> tuple[Path, Path]:
    """Write `<set>-<stamp>.md` and `.json`; returns both paths. `stamp` is chosen by the caller."""
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = out_dir / f"{summary.name}-{stamp}.md"
    data = out_dir / f"{summary.name}-{stamp}.json"
    markdown.write_text(render_markdown(results, summary), encoding="utf-8")
    data.write_text(render_json(results, summary), encoding="utf-8")
    return markdown, data
