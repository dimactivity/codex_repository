from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
