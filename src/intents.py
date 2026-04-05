from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Intent(str, Enum):
    CAPTURE = "capture"
    COMMAND = "command"
    COACH = "coach"
    REVIEW = "review"
    UNKNOWN = "unknown"


COMMAND_WORDS = {
    "найди",
    "извлеки",
    "покажи",
    "обнови",
    "измени",
    "удали",
    "delete",
    "find",
    "extract",
    "update",
}
COACH_WORDS = {"помоги", "посоветуй", "рефлексия", "стратегия", "как лучше", "coach"}
REVIEW_WORDS = {"review", "ревью", "итоги", "daily", "weekly"}


@dataclass
class ParsedRequest:
    intents: list[Intent]
    needs_clarification: bool


def parse_intents(text: str) -> ParsedRequest:
    t = text.lower().strip()
    detected: list[Intent] = []

    if any(word in t for word in REVIEW_WORDS):
        detected.append(Intent.REVIEW)
    if any(word in t for word in COMMAND_WORDS):
        detected.append(Intent.COMMAND)
    if any(word in t for word in COACH_WORDS):
        detected.append(Intent.COACH)

    # Capture — дефолт для произвольного контента/заметок
    if not detected:
        detected.append(Intent.CAPTURE)

    # Если слишком короткий и неочевидный запрос — уточняем
    needs_clarification = len(t) < 4 or detected == [Intent.UNKNOWN]

    return ParsedRequest(intents=detected, needs_clarification=needs_clarification)


def is_delete_request(text: str) -> bool:
    t = text.lower()
    return "удали" in t or "delete" in t


# Short-text ambiguity threshold: a soft hint, not a hard gate.
# Texts shorter than this with no explicit signal are treated as unclear.
_AMBIGUOUS_LEN = 8


def classify_intent(text: str) -> Literal["capture", "ask", "unclear"]:
    """Return a 3-way routing decision for confirmation UX.

    Priority (first match wins):
    1. COMMAND_WORDS present → ask
    2. Text ends with '?' → ask
    3. Very short text with no explicit signal → unclear (soft heuristic)
    4. Default → capture
    """
    t = text.strip()
    t_lower = t.lower()

    # Explicit ask signals win regardless of length.
    if any(word in t_lower for word in COMMAND_WORDS):
        return "ask"
    if t.endswith("?"):
        return "ask"

    # Short text with no clear signal is genuinely ambiguous.
    # This is a soft heuristic — single nouns or names may still lean toward
    # capture at the implementer's discretion; the threshold can be adjusted.
    if len(t) < _AMBIGUOUS_LEN:
        return "unclear"

    return "capture"
