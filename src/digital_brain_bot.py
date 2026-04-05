from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from intents import classify_intent
from storage import MarkdownStorage


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DATA_DIR = os.getenv("DATA_DIR", "./data")

storage = MarkdownStorage(DATA_DIR)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

_VALID_CALLBACK_DATA = {"cancel", "confirm_capture", "confirm_ask"}


def _ensure_token() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Fill .env first.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я Digital Brain — ваш второй мозг.\n"
        "Отправьте текст, и я помогу сохранить его или найти нужную информацию из сохранённого."
    )


# ---------------------------------------------------------------------------
# Ask output formatting — shared by /ask command and confirm_ask callback
# ---------------------------------------------------------------------------

def _clean_snippet(raw: str) -> str:
    """Strip technical leakage from a raw file snippet.

    Removes: frontmatter key-value lines, markdown headers (#),
    markdown separators (---), leading list markers (- ), bold/italic
    markers (**/**/*), and collapses blank lines.
    """
    lines = raw.splitlines()
    cleaned: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Frontmatter / metadata fields: "key: value" at line start
        if re.match(r"^\w[\w_]*:\s", s):
            continue
        # Markdown horizontal rules / YAML front-matter fences
        if re.match(r"^-{3,}$", s) or re.match(r"^\*{3,}$", s):
            continue
        # Markdown headers
        if s.startswith("#"):
            s = s.lstrip("#").strip()
        # Leading list markers
        if s.startswith("- "):
            s = s[2:].strip()
        # Bold/italic markers
        s = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", s)
        if s:
            cleaned.append(s)
    return " ".join(cleaned)


def _format_ask_results(results: list) -> str:
    """Format a list of SearchResult objects as a human-friendly Telegram message.

    Guarantees: no file paths, no frontmatter fields, no markdown noise.
    Returns a grounding line followed by clean excerpts in guillemet quotes.
    """
    n = len(results)
    grounding = f"Нашёл в 1 заметке:" if n == 1 else f"Нашёл в {n} заметках:"
    parts = [grounding]
    for r in results:
        clean = _clean_snippet(r.snippet)
        if clean:
            parts.append(f"«{clean}»")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Slash-command fallbacks (technical, not primary UX — must not regress)
# ---------------------------------------------------------------------------

async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Использование: /save <текст>")
        return
    path = storage.save_capture(content=text, source="telegram_text", user_id=update.effective_user.id)
    await update.message.reply_text(f"Сохранено: {path}")


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Использование: /ask <вопрос или запрос>")
        return

    results = storage.search(query, limit=5)
    if not results:
        await update.message.reply_text("Ничего не найдено в базе.")
        return

    await update.message.reply_text(_format_ask_results(results))


async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    period = (context.args[0].lower() if context.args else "daily").strip()
    if period not in {"daily", "weekly"}:
        await update.message.reply_text("Использование: /review daily|weekly")
        return
    path = storage.create_review(period=period, user_id=update.effective_user.id)
    await update.message.reply_text(f"Создан review: {path}")


# ---------------------------------------------------------------------------
# Intent-first text flow (Stage 2A): classify → store state → show buttons
# ---------------------------------------------------------------------------

def _build_keyboard(intent: str) -> InlineKeyboardMarkup:
    if intent == "capture":
        buttons = [
            InlineKeyboardButton("Отмена", callback_data="cancel"),
            InlineKeyboardButton("Сохранить", callback_data="confirm_capture"),
        ]
        return InlineKeyboardMarkup([buttons])
    if intent == "ask":
        buttons = [
            InlineKeyboardButton("Отмена", callback_data="cancel"),
            InlineKeyboardButton("Задать вопрос", callback_data="confirm_ask"),
        ]
        return InlineKeyboardMarkup([buttons])
    # unclear
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Отменить", callback_data="cancel"),
        InlineKeyboardButton("Сохранить в базу", callback_data="confirm_capture"),
        InlineKeyboardButton("Задать вопрос по базе", callback_data="confirm_ask"),
    ]])


def _confirmation_text(intent: str) -> str:
    if intent == "capture":
        return "Похоже, вы хотите сохранить это в Digital Brain."
    if intent == "ask":
        return "Похоже, вы хотите задать вопрос по сохранённым данным."
    return "Уточните, какое действие вы хотите совершить."


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    storage.log_operation(f"message_received | user_id={user_id} | len={len(text)}")

    intent = classify_intent(text)
    storage.log_operation(f"intent_detected | intent={intent} | user_id={user_id}")

    keyboard = _build_keyboard(intent)
    sent = await update.message.reply_text(_confirmation_text(intent), reply_markup=keyboard)

    # Store pending state for on_callback. Overwrites any previous pending
    # state — a new message always becomes the new independent input.
    context.user_data["pending_text"] = text
    context.user_data["pending_intent"] = intent
    context.user_data["pending_message_id"] = sent.message_id

    storage.log_operation(f"clarification_shown | intent={intent} | user_id={user_id}")


# ---------------------------------------------------------------------------
# Callback handler (Stage 2B): read state, guard stale, execute, reset
# ---------------------------------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id

    # Always answer the callback query first to dismiss the loading spinner.
    await query.answer()

    data = query.data
    pending_text: str | None = context.user_data.get("pending_text")
    pending_message_id: int | None = context.user_data.get("pending_message_id")

    # --- Stale / invalid guard ---

    if pending_text is None:
        await query.message.reply_text("Действие устарело. Отправьте сообщение заново.")
        return

    if query.message.message_id != pending_message_id:
        # A new message replaced the pending state; this button is stale.
        _clear_pending(context)
        await query.message.reply_text("Действие устарело. Отправьте сообщение заново.")
        return

    if data not in _VALID_CALLBACK_DATA:
        storage.log_operation(f"error | handler=on_callback | unexpected callback_data={data!r}")
        _clear_pending(context)
        await query.message.reply_text("Неизвестное действие. Отправьте сообщение заново.")
        return

    # --- Valid action ---

    storage.log_operation(f"user_action_selected | action={data} | user_id={user_id}")

    if data == "cancel":
        _clear_pending(context)
        await query.message.reply_text("Отменено.")
        return

    if data == "confirm_capture":
        try:
            path = storage.save_capture(
                content=pending_text,
                source="telegram_text",
                user_id=user_id,
            )
            storage.log_operation(f"capture_saved | path={path}")
            _clear_pending(context)
            await query.message.reply_text("Сохранено.")
        except Exception as exc:
            storage.log_operation(f"error | handler=on_callback | err={exc}")
            _clear_pending(context)
            await query.message.reply_text("Не удалось сохранить. Попробуйте ещё раз.")
        return

    if data == "confirm_ask":
        try:
            results = storage.search(pending_text, limit=5)
            storage.log_operation(
                f"ask_executed | query={pending_text!r} | result_count={len(results)}"
            )
            _clear_pending(context)
            if not results:
                await query.message.reply_text("Ничего не найдено в базе.")
            else:
                await query.message.reply_text(_format_ask_results(results))
            storage.log_operation(f"answer_returned | result_count={len(results)}")
        except Exception as exc:
            storage.log_operation(f"error | handler=on_callback | err={exc}")
            _clear_pending(context)
            await query.message.reply_text("Ошибка при поиске. Попробуйте ещё раз.")


def _clear_pending(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_text", None)
    context.user_data.pop("pending_intent", None)
    context.user_data.pop("pending_message_id", None)


# ---------------------------------------------------------------------------
# Voice handler — unchanged; routes directly to save_capture (Phase 3 later)
# ---------------------------------------------------------------------------

async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice
    if not voice:
        return

    if not openai_client:
        await update.message.reply_text(
            "OPENAI_API_KEY не задан. Пока могу сохранять только текст."
        )
        return

    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        temp_path = Path(tmp.name)

    await file.download_to_drive(custom_path=str(temp_path))

    try:
        with temp_path.open("rb") as f:
            transcript = openai_client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=f)
        text = (transcript.text or "").strip()
        if not text:
            await update.message.reply_text("Не удалось распознать голосовое.")
            return

        path = storage.save_capture(content=text, source="telegram_voice_transcript", user_id=update.effective_user.id)
        await update.message.reply_text(f"Голосовое распознано и сохранено: {path}")
    finally:
        temp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _ensure_token()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("review", review_cmd))
    # Callback handler registered after commands, before free-text.
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Digital Brain bot is running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
