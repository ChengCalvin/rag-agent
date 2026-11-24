"""Final reply assembly in code (task 6.4, D15, D17, AGENT-3).

The reply on every route is body text (composer text or canned wording), optional notes, the
Sources list, the confidence band and the cost line, joined here. Wording that is policy or
user-facing prose (limitation sentence, synthetic-policy note, declines) is passed in by the
caller from `prompts/`; this module only lays it out. The labels `Sources:` and `Confidence:`
are layout, not policy.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from novamart_agent.models import ConfidenceBand, SourceEntry

SOURCES_LABEL = "Sources:"
CONFIDENCE_LABEL = "Confidence:"


@dataclass(frozen=True)
class ReplyParts:
    """The pieces of one reply. `notes` are canned sentences placed right after the body, in
    order; `band` is None on routes with no confidence band (order, declines)."""

    body: str
    sources: tuple[SourceEntry, ...] = ()
    band: ConfidenceBand | None = None
    notes: tuple[str, ...] = ()
    cost_line: str | None = None


def format_source(entry: SourceEntry) -> str:
    """`- Title, section "Heading" (path)`, or `- Title (path)` when there is no heading."""
    heading = f', section "{entry.heading}"' if entry.heading else ""
    return f"- {entry.title}{heading} ({entry.path})"


def _sources_block(sources: Sequence[SourceEntry]) -> str | None:
    if not sources:
        return None
    return "\n".join([SOURCES_LABEL, *(format_source(s) for s in sources)])


def assemble_reply(parts: ReplyParts) -> str:
    """Join the pieces with blank lines; absent pieces are left out."""
    band = f"{CONFIDENCE_LABEL} {parts.band.value}" if parts.band else None
    sources = _sources_block(parts.sources)
    pieces = [parts.body.strip(), *parts.notes, sources, band, parts.cost_line]
    return "\n\n".join(p.strip() for p in pieces if p and p.strip())
