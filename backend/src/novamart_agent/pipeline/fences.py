"""Split text into plain and fenced-code segments, keeping every original line.

Used by the output check to compare a reply's fenced blocks with the retrieved chunks. Unlike
`rag.fenced_blocks` (a loader that rejects a truncated fence), this scanner never raises: an
unclosed fence in a model reply is returned as an unclosed segment so the caller can strip it.
`pipeline/` may not import `rag/` (same layer, ARCH-LAYER-3), hence its own small scanner.

Fences follow CommonMark: three or more backticks or tildes, indented by at most three spaces; a
fence of N markers closes only on a line of at least N of the same marker and nothing else. A
line that starts a backtick run in the middle of prose (an inline opener such as "see ```x") also
opens a block, flagged `inline`, so the whole block is stripped and its body never leaks as a
valid-looking diagram.
"""

import re
from dataclasses import dataclass

_OPENER = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_BACKTICK_RUN = re.compile(r"`{3,}")


@dataclass(frozen=True)
class Segment:
    """A run of lines: either plain text or one fenced block (fence lines included)."""

    lines: tuple[str, ...]
    is_fence: bool
    closed: bool = True
    inline: bool = False

    @property
    def inner(self) -> str:
        """The block's content without the fence lines, trailing spaces and edge blanks removed.

        Empty for a plain segment. Used as the comparison key for the verbatim check.
        """
        if not self.is_fence:
            return ""
        body = self.lines[1:-1] if self.closed else self.lines[1:]
        return "\n".join(line.rstrip() for line in body).strip("\n")


@dataclass(frozen=True)
class _Open:
    marker: str
    size: int
    inline: bool = False

    def closes(self, line: str) -> bool:
        if self.inline:
            return re.search(f"{re.escape(self.marker)}{{{self.size},}}", line) is not None
        pattern = f"^ {{0,3}}{re.escape(self.marker)}{{{self.size},}}[ \\t]*$"
        return re.match(pattern, line) is not None


def _opening(line: str) -> _Open | None:
    match = _OPENER.match(line)
    if match is not None:
        run, info = match.groups()
        if not (run[0] == "`" and "`" in info):  # a backtick fence's info has no backtick
            return _Open(run[0], len(run))
    runs = _BACKTICK_RUN.findall(line)
    if len(runs) % 2 == 1:  # an unmatched run: a code span or fence opened mid-line
        return _Open("`", len(runs[-1]), inline=True)
    return None


def split_fences(text: str) -> list[Segment]:
    """Segments in order; concatenating their lines gives back `text.splitlines()`."""
    segments: list[Segment] = []
    plain: list[str] = []
    fence: list[str] | None = None
    opened: _Open | None = None
    for line in text.splitlines():
        if opened is None:
            opened = _opening(line)
            if opened is None:
                plain.append(line)
                continue
            if plain:
                segments.append(Segment(tuple(plain), False))
                plain = []
            fence = [line]
        elif fence is not None:
            fence.append(line)
            if opened.closes(line):
                segments.append(Segment(tuple(fence), True, inline=opened.inline))
                fence, opened = None, None
    if plain:
        segments.append(Segment(tuple(plain), False))
    if fence is not None and opened is not None:
        segments.append(Segment(tuple(fence), True, closed=False, inline=opened.inline))
    return segments


def block_keys(text: str) -> set[str]:
    """Comparison keys of every closed, line-start fenced block in `text`."""
    return {s.inner for s in split_fences(text) if s.is_fence and s.closed and not s.inline}
