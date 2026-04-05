from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _make_update(text: str = "test", user_id: int = 42, message_id: int = 1) -> MagicMock:
    """Build a minimal fake Update for a text message."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.message_id = message_id
    update.message.reply_text = AsyncMock(
        return_value=MagicMock(message_id=message_id + 100)
    )
    return update


def _make_context(user_data: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    return ctx


def _make_callback_update(
    data: str,
    bot_message_id: int = 101,
    user_id: int = 42,
) -> MagicMock:
    """Build a minimal fake Update for a callback query."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.message.message_id = bot_message_id
    update.callback_query.message.reply_text = AsyncMock()
    return update


class OnTextCaptureFlowTests(unittest.IsolatedAsyncioTestCase):

    async def test_capture_intent_stores_pending_and_sends_buttons(self) -> None:
        from digital_brain_bot import on_text

        update = _make_update("Купить молоко и хлеб")
        ctx = _make_context()

        with patch("digital_brain_bot.classify_intent", return_value="capture"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update, ctx)

        self.assertEqual(ctx.user_data["pending_text"], "Купить молоко и хлеб")
        self.assertEqual(ctx.user_data["pending_intent"], "capture")
        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args
        self.assertIn("reply_markup", call_kwargs.kwargs)

    async def test_ask_intent_stores_pending_and_sends_buttons(self) -> None:
        from digital_brain_bot import on_text

        update = _make_update("найди записи про кофе")
        ctx = _make_context()

        with patch("digital_brain_bot.classify_intent", return_value="ask"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update, ctx)

        self.assertEqual(ctx.user_data["pending_intent"], "ask")

    async def test_unclear_intent_stores_pending_and_sends_buttons(self) -> None:
        from digital_brain_bot import on_text

        update = _make_update("да")
        ctx = _make_context()

        with patch("digital_brain_bot.classify_intent", return_value="unclear"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update, ctx)

        self.assertEqual(ctx.user_data["pending_intent"], "unclear")
        update.message.reply_text.assert_called_once()

    async def test_pending_message_id_stored(self) -> None:
        from digital_brain_bot import on_text

        update = _make_update("заметка")
        sent_msg = MagicMock(message_id=999)
        update.message.reply_text = AsyncMock(return_value=sent_msg)
        ctx = _make_context()

        with patch("digital_brain_bot.classify_intent", return_value="capture"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update, ctx)

        self.assertEqual(ctx.user_data["pending_message_id"], 999)

    async def test_new_message_overwrites_pending_state(self) -> None:
        from digital_brain_bot import on_text

        # First message
        update1 = _make_update("первая заметка")
        update1.message.reply_text = AsyncMock(return_value=MagicMock(message_id=101))
        ctx = _make_context()

        with patch("digital_brain_bot.classify_intent", return_value="capture"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update1, ctx)

        self.assertEqual(ctx.user_data["pending_text"], "первая заметка")

        # Second message — should replace the first
        update2 = _make_update("вторая заметка")
        update2.message.reply_text = AsyncMock(return_value=MagicMock(message_id=202))

        with patch("digital_brain_bot.classify_intent", return_value="capture"), \
             patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_text(update2, ctx)

        self.assertEqual(ctx.user_data["pending_text"], "вторая заметка")
        self.assertEqual(ctx.user_data["pending_message_id"], 202)


class OnCallbackCancelTests(unittest.IsolatedAsyncioTestCase):

    async def test_cancel_clears_state_and_does_not_save(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "заметка",
            "pending_intent": "capture",
            "pending_message_id": 101,
        })
        update = _make_callback_update("cancel", bot_message_id=101)

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.save_capture.assert_not_called()
        self.assertNotIn("pending_text", ctx.user_data)
        update.callback_query.message.reply_text.assert_called_once()
        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("Отменено", reply_text)


class OnCallbackConfirmCaptureTests(unittest.IsolatedAsyncioTestCase):

    async def test_confirm_capture_calls_save_and_clears_state(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "Купить молоко",
            "pending_intent": "capture",
            "pending_message_id": 101,
        })
        update = _make_callback_update("confirm_capture", bot_message_id=101, user_id=42)

        mock_path = Path("/fake/data/inbox/note.md")

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.save_capture.return_value = mock_path
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.save_capture.assert_called_once_with(
            content="Купить молоко",
            source="telegram_text",
            user_id=42,
        )
        self.assertNotIn("pending_text", ctx.user_data)
        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("Сохранено", reply_text)


class OnCallbackConfirmAskTests(unittest.IsolatedAsyncioTestCase):

    async def test_confirm_ask_calls_search_and_clears_state(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "найди кофе",
            "pending_intent": "ask",
            "pending_message_id": 101,
        })
        update = _make_callback_update("confirm_ask", bot_message_id=101)

        fake_result = MagicMock()
        fake_result.path = Path("/data/inbox/note.md")
        fake_result.snippet = "кофе заметка"

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.search.return_value = [fake_result]
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.search.assert_called_once_with("найди кофе", limit=5)
        self.assertNotIn("pending_text", ctx.user_data)

    async def test_confirm_ask_no_results_replies_gracefully(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "нет такого",
            "pending_intent": "ask",
            "pending_message_id": 101,
        })
        update = _make_callback_update("confirm_ask", bot_message_id=101)

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.search.return_value = []
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("не найдено", reply_text.lower())


class OnCallbackStaleTests(unittest.IsolatedAsyncioTestCase):

    async def test_no_pending_state_replies_stale(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({})  # no pending state
        update = _make_callback_update("confirm_capture", bot_message_id=101)

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.save_capture = MagicMock()
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.save_capture.assert_not_called()
        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("устарело", reply_text.lower())

    async def test_mismatched_message_id_replies_stale(self) -> None:
        from digital_brain_bot import on_callback

        # pending_message_id=101, but callback comes from message 202 (old button)
        ctx = _make_context({
            "pending_text": "новая заметка",
            "pending_intent": "capture",
            "pending_message_id": 101,
        })
        update = _make_callback_update("confirm_capture", bot_message_id=202)

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.save_capture = MagicMock()
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.save_capture.assert_not_called()
        self.assertNotIn("pending_text", ctx.user_data)
        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("устарело", reply_text.lower())

    async def test_unexpected_callback_data_replies_unknown(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "заметка",
            "pending_intent": "capture",
            "pending_message_id": 101,
        })
        update = _make_callback_update("totally_unexpected", bot_message_id=101)

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.save_capture = MagicMock()
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        mock_storage.save_capture.assert_not_called()
        self.assertNotIn("pending_text", ctx.user_data)
        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertIn("неизвестное", reply_text.lower())


class AskOutputFormatTests(unittest.TestCase):
    """Unit tests for _format_ask_results() — no file paths, no markdown noise,
    no frontmatter leakage, grounding line present."""

    def _result(self, snippet: str, path: str = "/data/inbox/20260405_140000_000000_42.md") -> MagicMock:
        r = MagicMock()
        r.path = Path(path)
        r.snippet = snippet
        r.score = 1
        return r

    def test_no_file_paths_in_output(self) -> None:
        from digital_brain_bot import _format_ask_results
        text = _format_ask_results([self._result("кофе помогает сосредоточиться")])
        self.assertNotIn(".md", text)
        self.assertNotRegex(text, r"data/inbox")
        self.assertNotRegex(text, r"data/reviews")

    def test_no_frontmatter_source_field(self) -> None:
        from digital_brain_bot import _format_ask_results
        snippet = "source: telegram_text\ncreated_at_utc: 2026-04-05T10:00:00\nuser_id: 42\nкофе заметка"
        text = _format_ask_results([self._result(snippet)])
        import re
        self.assertNotRegex(text, r"(?m)^source:")
        self.assertNotRegex(text, r"(?m)^created_at_utc:")
        self.assertNotRegex(text, r"(?m)^user_id:")

    def test_no_markdown_headers(self) -> None:
        from digital_brain_bot import _format_ask_results
        snippet = "# Заголовок заметки\nнормальный текст"
        text = _format_ask_results([self._result(snippet)])
        self.assertNotRegex(text, r"(?m)^#")

    def test_no_markdown_separators(self) -> None:
        from digital_brain_bot import _format_ask_results
        snippet = "---\nнормальный текст"
        text = _format_ask_results([self._result(snippet)])
        self.assertNotIn("---", text)

    def test_no_markdown_list_markers(self) -> None:
        from digital_brain_bot import _format_ask_results
        snippet = "- пункт списка\nнормальный текст"
        text = _format_ask_results([self._result(snippet)])
        self.assertNotRegex(text, r"(?m)^- ")

    def test_grounding_line_singular(self) -> None:
        from digital_brain_bot import _format_ask_results
        text = _format_ask_results([self._result("кофе заметка")])
        self.assertIn("Нашёл в", text)
        self.assertIn("1", text)

    def test_grounding_line_plural(self) -> None:
        from digital_brain_bot import _format_ask_results
        results = [self._result("первая заметка"), self._result("вторая заметка")]
        text = _format_ask_results(results)
        self.assertIn("Нашёл в", text)
        self.assertIn("2", text)

    def test_snippet_content_present(self) -> None:
        from digital_brain_bot import _format_ask_results
        text = _format_ask_results([self._result("уникальный текст про кофе")])
        self.assertIn("уникальный текст про кофе", text)


class AskOutputWiringTests(unittest.IsolatedAsyncioTestCase):
    """Integration tests — verify the formatter is wired through both
    the confirm_ask callback and the /ask slash command."""

    async def test_confirm_ask_reply_has_no_file_paths(self) -> None:
        from digital_brain_bot import on_callback

        ctx = _make_context({
            "pending_text": "найди кофе",
            "pending_intent": "ask",
            "pending_message_id": 101,
        })
        update = _make_callback_update("confirm_ask", bot_message_id=101)

        fake_result = MagicMock()
        fake_result.path = Path("/data/inbox/20260405_note.md")
        fake_result.snippet = "кофе помогает сосредоточиться"
        fake_result.score = 1

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.search.return_value = [fake_result]
            mock_storage.log_operation = MagicMock()
            await on_callback(update, ctx)

        reply_text = update.callback_query.message.reply_text.call_args.args[0]
        self.assertNotIn(".md", reply_text)
        self.assertIn("Нашёл в", reply_text)

    async def test_ask_cmd_reply_has_no_file_paths(self) -> None:
        from digital_brain_bot import ask_cmd

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = ["кофе"]

        fake_result = MagicMock()
        fake_result.path = Path("/data/inbox/20260405_note.md")
        fake_result.snippet = "кофе помогает сосредоточиться"
        fake_result.score = 1

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.search.return_value = [fake_result]
            await ask_cmd(update, ctx)

        reply_text = update.message.reply_text.call_args.args[0]
        self.assertNotIn(".md", reply_text)
        self.assertIn("Нашёл в", reply_text)


class SlashCommandCompatibilityTests(unittest.IsolatedAsyncioTestCase):

    async def test_save_cmd_calls_save_capture(self) -> None:
        from digital_brain_bot import save_cmd

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 42
        ctx = MagicMock()
        ctx.args = ["тест", "заметка"]

        mock_path = Path("/fake/data/inbox/note.md")

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.save_capture.return_value = mock_path
            await save_cmd(update, ctx)

        mock_storage.save_capture.assert_called_once_with(
            content="тест заметка",
            source="telegram_text",
            user_id=42,
        )

    async def test_ask_cmd_calls_search(self) -> None:
        from digital_brain_bot import ask_cmd

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 42
        ctx = MagicMock()
        ctx.args = ["молоко"]

        fake_result = MagicMock()
        fake_result.path = Path("/data/inbox/note.md")
        fake_result.snippet = "молоко купить"

        with patch("digital_brain_bot.storage") as mock_storage:
            mock_storage.search.return_value = [fake_result]
            await ask_cmd(update, ctx)

        mock_storage.search.assert_called_once_with("молоко", limit=5)


if __name__ == "__main__":
    unittest.main()
