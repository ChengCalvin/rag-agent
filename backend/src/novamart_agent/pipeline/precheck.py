"""Input precheck: empty, over-length and known injection patterns (task 6.2, D10, ARCH-BOUND-1 d).

Pure and run before any model call. It never inspects order ids: a malformed id such as `10x2`
is not a reason to decline here, because the order tool rejects it with the same not-found text
as a nonexistent order, so the whole turn makes the same calls either way (AG-43, D13 case D).
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from novamart_agent.config import PipelineSettings


class PrecheckReason(StrEnum):
    """Why a message was declined."""

    EMPTY = "empty"
    TOO_LONG = "too_long"
    INJECTION = "injection"


@dataclass(frozen=True)
class PrecheckResult:
    """`reason` is None when the message may proceed to intake."""

    reason: PrecheckReason | None

    @property
    def proceed(self) -> bool:
        """True when no precheck rule fired."""
        return self.reason is None


# Known instruction-override and role-claim phrasings, matched on the normalised message
# (NFKC, case-folded, whitespace collapsed, zero-width characters removed). A defence in depth
# only: the guarantees live in tool-side authorization (D2, D3), not here. Each pattern needs an
# instruction target ("your", "previous", "above", "system" ...), so a store question such as
# "Can staff ignore the return rules?" or "What is the debug mode on the POS?" proceeds.
_NOUN = r"(instructions?|rules?|prompts?|restrictions?|guidelines?|directions?)"
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"\b(ignore|disregard|forget|override)\s+(?:(?:the|all|any|of)\s+)*"
        rf"(?:(?:your|previous|prior|above|earlier|preceding|system|safety)\s+)+{_NOUN}\b",
        rf"\b(ignore|disregard|forget)\s+(?:all|every|any)\s+(?:of\s+)?(?:the\s+)?{_NOUN}\b",
        r"\boverride\b.{0,30}\b(store|access|permission|security)\b.{0,15}\b(restriction|limit)s?\b",
        r"\b(reveal|show|print|repeat|output)\s+(?:(?:me|us)\s+)?(?:(?:the|your)\s+)?"
        r"(?:system|hidden|initial)\s+(?:prompt|instructions?)\b",
        r"\byou are now (an?|the|my|dan|free|unrestricted|no longer|in)\b",
        r"\b(enable|enter|activate|switch to|turn on)\s+(developer|jailbreak|dan|god) mode\b",
        r"\bpretend (to be|you are|you're)\b",
    )
)


def _normalise(message: str) -> str:
    folded = unicodedata.normalize("NFKC", message).casefold()
    visible = "".join(c for c in folded if unicodedata.category(c) != "Cf")
    return " ".join(visible.split())


def precheck(message: str, settings: PipelineSettings) -> PrecheckResult:
    """Decide whether `message` may reach intake."""
    normalised = _normalise(message)
    if not normalised:
        return PrecheckResult(PrecheckReason.EMPTY)
    if len(message) > settings.max_message_chars:
        return PrecheckResult(PrecheckReason.TOO_LONG)
    if any(p.search(normalised) for p in _INJECTION_PATTERNS):
        return PrecheckResult(PrecheckReason.INJECTION)
    return PrecheckResult(None)
