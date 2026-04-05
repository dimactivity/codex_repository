from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from intents import Intent, ParsedRequest, classify_intent, parse_intents


class ClassifyIntentAskTests(unittest.TestCase):
    """Explicit ask signals must win regardless of text length."""

    def test_command_word_найди(self) -> None:
        self.assertEqual(classify_intent("найди записи про кофе"), "ask")

    def test_command_word_покажи(self) -> None:
        self.assertEqual(classify_intent("покажи все заметки"), "ask")

    def test_command_word_find(self) -> None:
        self.assertEqual(classify_intent("find notes about coffee"), "ask")

    def test_command_word_extract(self) -> None:
        self.assertEqual(classify_intent("extract ideas"), "ask")

    def test_question_mark_long(self) -> None:
        self.assertEqual(classify_intent("что я думал про проект?"), "ask")

    def test_question_mark_short(self) -> None:
        # Explicit ask marker wins even when text is very short.
        self.assertEqual(classify_intent("как?"), "ask")

    def test_command_word_short_text(self) -> None:
        # COMMAND_WORD in short text still routes to ask.
        self.assertEqual(classify_intent("найди"), "ask")


class ClassifyIntentCaptureTests(unittest.TestCase):
    """Long notes with no ask signals should be capture."""

    def test_long_note(self) -> None:
        self.assertEqual(classify_intent("Купить молоко, хлеб и масло"), "capture")

    def test_long_note_no_keywords(self) -> None:
        self.assertEqual(classify_intent("Сегодня провёл хорошую встречу с командой"), "capture")

    def test_english_statement(self) -> None:
        self.assertEqual(classify_intent("Interesting idea about distributed systems"), "capture")


class ClassifyIntentUnclearTests(unittest.TestCase):
    """Non-content tokens that cannot be interpreted without asking the user."""

    def test_token_да(self) -> None:
        self.assertEqual(classify_intent("да"), "unclear")

    def test_token_ок(self) -> None:
        self.assertEqual(classify_intent("ок"), "unclear")

    def test_token_yes(self) -> None:
        self.assertEqual(classify_intent("yes"), "unclear")

    def test_token_hi(self) -> None:
        self.assertEqual(classify_intent("hi"), "unclear")

    def test_token_привет(self) -> None:
        self.assertEqual(classify_intent("привет"), "unclear")

    def test_token_нет(self) -> None:
        self.assertEqual(classify_intent("нет"), "unclear")

    def test_token_no(self) -> None:
        self.assertEqual(classify_intent("no"), "unclear")

    def test_token_ok(self) -> None:
        self.assertEqual(classify_intent("ok"), "unclear")


class ClassifyIntentCaptureShortInputTests(unittest.TestCase):
    """Short but meaningful inputs must NOT be routed to unclear — they are captures."""

    def test_short_noun_молоко(self) -> None:
        # Single meaningful word is a valid note, not ambiguous.
        self.assertEqual(classify_intent("молоко"), "capture")

    def test_short_note_хлб(self) -> None:
        self.assertEqual(classify_intent("хлб"), "capture")

    def test_short_word_идея(self) -> None:
        self.assertEqual(classify_intent("идея"), "capture")


class ClassifyIntentQuestionStarterTests(unittest.TestCase):
    """Question-starter words route to ask even without a trailing '?'."""

    def test_starter_что(self) -> None:
        self.assertEqual(classify_intent("что делать с задачей"), "ask")

    def test_starter_как(self) -> None:
        self.assertEqual(classify_intent("как это работает"), "ask")

    def test_starter_где(self) -> None:
        self.assertEqual(classify_intent("где мои заметки про кофе"), "ask")

    def test_starter_когда(self) -> None:
        self.assertEqual(classify_intent("когда я это записал"), "ask")

    def test_starter_зачем(self) -> None:
        self.assertEqual(classify_intent("зачем я это добавил"), "ask")

    def test_starter_почему(self) -> None:
        self.assertEqual(classify_intent("почему это важно"), "ask")

    def test_starter_скажи(self) -> None:
        self.assertEqual(classify_intent("скажи что я знаю про архитектуру"), "ask")

    def test_starter_расскажи(self) -> None:
        self.assertEqual(classify_intent("расскажи про мои заметки"), "ask")


class ClassifyIntentEdgeCaseTests(unittest.TestCase):
    """Edge cases: explicit signals always win; no length-based rules."""

    def test_long_text_with_question_mark(self) -> None:
        self.assertEqual(classify_intent("Что я записывал про встречу на прошлой неделе?"), "ask")

    def test_command_word_mid_sentence(self) -> None:
        self.assertEqual(classify_intent("пожалуйста найди всё про задачу"), "ask")

    def test_empty_string(self) -> None:
        self.assertEqual(classify_intent(""), "unclear")

    def test_whitespace_only(self) -> None:
        self.assertEqual(classify_intent("   "), "unclear")


class ParseIntentsSmokeTest(unittest.TestCase):
    """Confirm parse_intents() still returns ParsedRequest and is not broken."""

    def test_returns_parsed_request(self) -> None:
        result = parse_intents("купить молоко")
        self.assertIsInstance(result, ParsedRequest)
        self.assertIsInstance(result.intents, list)
        self.assertIsInstance(result.needs_clarification, bool)

    def test_default_capture_intent(self) -> None:
        result = parse_intents("купить молоко")
        self.assertIn(Intent.CAPTURE, result.intents)

    def test_command_word_routes_to_command(self) -> None:
        result = parse_intents("найди записи")
        self.assertIn(Intent.COMMAND, result.intents)


if __name__ == "__main__":
    unittest.main()
