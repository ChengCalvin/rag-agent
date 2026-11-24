"""Checks on model-written reply text (task 6.4, D15, AGENT-3).

Two things the model may not do: write citations, a band or a cost (code appends them), and
include a diagram that is not in the retrieved chunks. `sanitize_model_text` removes any
Sources, Confidence or Cost lines and every fenced block that does not appear verbatim in a
retrieved chunk.
"""

import re
import unicodedata
from collections.abc import Sequence

from novamart_agent.pipeline.fences import Segment, block_keys, split_fences

# A line that starts a citation, band or cost section: "Sources:", "**Confidence**: High",
# "Confidence - High", ... Matched on the line after `_fold` (NFKC, zero-width characters gone).
_FOOTER_LINE = re.compile(
    r"^[\s>#*_-]*(sources?|references?|citations?|confidence|cost)\b[\s*_]*(:|\s[-–—]\s|$)",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*([-*•]|\d+[.)])\s")


def _fold(line: str) -> str:
    """NFKC-normalise and drop format characters (zero-width space, joiners, BOM)."""
    folded = unicodedata.normalize("NFKC", line)
    return "".join(c for c in folded if unicodedata.category(c) != "Cf")


def _strip_footer_lines(lines: Sequence[str]) -> list[str]:
    """Drop footer-style lines, and the bullet lines that directly follow one."""
    kept: list[str] = []
    in_footer = False
    for line in lines:
        if _FOOTER_LINE.match(_fold(line)):
            in_footer = True
        elif in_footer and _BULLET.match(line):
            pass
        else:
            in_footer = False
            kept.append(line)
    return kept


def _keep(segment: Segment, verified: set[str]) -> bool:
    return not segment.is_fence or (
        segment.closed and not segment.inline and segment.inner in verified
    )


def sanitize_model_text(text: str, chunk_texts: Sequence[str]) -> str:
    """Return `text` without model-written footers and without unverified diagrams.

    A fenced block survives only when its content equals (ignoring trailing spaces and edge
    blank lines) a fenced block of one of `chunk_texts`. Fenced content is never scanned for
    footers, so a verified diagram is returned unchanged.
    """
    verified: set[str] = set()
    for chunk_text in chunk_texts:
        verified |= block_keys(chunk_text)
    out: list[str] = []
    for segment in split_fences(text):
        if not _keep(segment, verified):
            continue
        out.extend(segment.lines if segment.is_fence else _strip_footer_lines(segment.lines))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
