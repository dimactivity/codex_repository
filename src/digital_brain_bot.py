from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from intents import Intent, is_delete_request, parse_intents
from storage import MarkdownStorage


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DATA_DIR = os.getenv("DATA_DIR", "./data")

storage = MarkdownStorage(DATA_DIR)
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _ensure_token() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Fill .env first.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я Digital Brain MVP.\n"
        "Отправь текст/голос, и я сохраню это в markdown.\n"
        "Команды: /save, /ask, /review daily|weekly"
    )


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

    lines = ["Найдено:"]
    for r in results:
        lines.append(f"- {r.path}: {r.snippet[:140]}...")
    await update.message.reply_text("\n".join(lines))


async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    period = (context.args[0].lower() if context.args else "daily").strip()
    if period not in {"daily", "weekly"}:
        await update.message.reply_text("Использование: /review daily|weekly")
        return
    path = storage.create_review(period=period, user_id=update.effective_user.id)
    await update.message.reply_text(f"Создан review: {path}")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    parsed = parse_intents(text)

    if parsed.needs_clarification:
        await update.message.reply_text("Уточни, пожалуйста: сохранить, извлечь или обсудить?")
        return

    if is_delete_request(text):
        await update.message.reply_text(
            "Обнаружен запрос на удаление. Подтверди явно: YES_DELETE <что удалить>"
        )
        return

    handled = []
    for intent in parsed.intents:
        if intent == Intent.CAPTURE:
            path = storage.save_capture(text, source="telegram_text", user_id=update.effective_user.id)
            handled.append(f"capture -> {path}")
        elif intent == Intent.COMMAND:
            results = storage.search(text, limit=3)
            if results:
                handled.append("command/search -> " + ", ".join(str(r.path) for r in results))
            else:
                handled.append("command/search -> no results")
        elif intent == Intent.COACH:
            handled.append("coach -> рекомендация: сформулируй цель, ограничения и горизонт планирования")
        elif intent == Intent.REVIEW:
            path = storage.create_review("daily", user_id=update.effective_user.id)
            handled.append(f"review -> {path}")

    await update.message.reply_text("Выполнено:\n" + "\n".join(f"- {h}" for h in handled))


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


def main() -> None:
    _ensure_token()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("review", review_cmd))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Digital Brain bot is running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
