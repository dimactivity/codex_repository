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


# NOTE: reserved for future multi-intent UI — not called by the bot.
# classify_intent() below is the active routing function.
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


# Tokens that carry no intent — sending one of these alone means the
# user's goal cannot be determined without asking.  Keep this list small
# and add to it only when a token is genuinely content-free.
_UNCLEAR_TOKENS = {
    "да", "нет", "ок", "окей", "ладно", "хорошо",
    "yes", "no", "ok", "okay", "sure", "yep", "nope",
    "hi", "hello", "привет", "хай",
}

# Russian question-starter words that signal a query even without '?'.
# Scoped to common single-word starters — not full phrase matching.
_QUESTION_STARTERS = {
    "что", "как", "где", "когда", "зачем", "почему",
    "скажи", "расскажи",
}


def classify_intent(text: str) -> Literal["capture", "ask", "unclear"]:
    """Return a 3-way routing decision for the confirmation UX.

    Decision logic (first match wins — no length thresholds):

    1. COMMAND_WORDS present → "ask"
       (найди, покажи, find, extract, …)
    2. Text ends with "?" → "ask"
    3. Text starts with a question-starter word → "ask"
       (что, как, где, когда, зачем, почему, скажи, расскажи)
    4. Text (stripped, lowercased) matches an explicit non-content token → "unclear"
       (да, нет, ок, yes, no, ok, hi, привет, …)
    5. Empty / whitespace-only → "unclear"
    6. Default → "capture"

    To tune routing: extend COMMAND_WORDS, _QUESTION_STARTERS, or
    _UNCLEAR_TOKENS — do not add length-based conditions.
    """
    t = text.strip()
    t_lower = t.lower()

    if not t:
        return "unclear"

    # Explicit search/command words → ask.
    if any(word in t_lower for word in COMMAND_WORDS):
        return "ask"

    # Question mark at end → ask.
    if t.endswith("?"):
        return "ask"

    # Question-starter as first word → ask.
    first_word = t_lower.split()[0]
    if first_word in _QUESTION_STARTERS:
        return "ask"

    # Known non-content tokens → unclear.
    if t_lower in _UNCLEAR_TOKENS:
        return "unclear"

    return "capture"
