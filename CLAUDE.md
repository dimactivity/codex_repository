# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
./scripts/bootstrap.sh        # create .venv, install deps, copy .env.example → .env
source .venv/bin/activate
# edit .env: set TELEGRAM_BOT_TOKEN (required), OPENAI_API_KEY (optional, for voice)
```

## Running

```bash
python src/digital_brain_bot.py   # start the bot
./scripts/run_local.sh            # config check + start
```

## Tests

```bash
python -m pytest tests/                   # run all tests
python -m pytest tests/test_storage.py   # run a single file
```

`sys.path` is patched inside tests to import from `src/` directly — no package install needed.

## Architecture

This is a Telegram bot that acts as a personal "digital brain": it receives text/voice messages, classifies them by intent, and stores everything as Markdown files on disk (no database).

**Request flow:**

1. `digital_brain_bot.py` — entry point and orchestration. Free-text messages go through `classify_intent()` → pending state → confirmation buttons → `on_callback()`. `_format_ask_results()` formats search output (no file paths, no markdown noise). Explicit commands (`/save`, `/ask`, `/review`) bypass intent detection.
2. `intents.py` — semantic signal-based intent classifier. `classify_intent()` returns `"capture"`, `"ask"`, or `"unclear"` using COMMAND_WORDS, question-mark suffix, question-starter words, and an explicit non-content token list — no length thresholds. `parse_intents()` is defined but reserved for a future multi-intent UI; it is not called by the bot.
3. `storage.py` — all disk I/O. `MarkdownStorage` writes captures to `data/inbox/`, reviews to `data/reviews/`, and appends every operation to `data/logs/operations.md`. `search()` does a simple term-frequency scan across all `.md` files. File uniqueness on timestamp collisions is handled by `_resolve_unique_path()`.

**Data layout (`data/`):**
- `inbox/` — capture notes, filename: `YYYYMMDD_HHMMSS_µs_<user_id>.md`
- `reviews/` — daily/weekly templates, filename: `daily_YYYYMMDD_<user_id>.md` (versioned `_v2`, `_v3` on same-day repeats)
- `logs/operations.md` — append-only audit log; excluded from search results
- `entities/` — reserved for future structured entities (currently unused)

**Environment variables** (`.env`):
- `TELEGRAM_BOT_TOKEN` — required
- `OPENAI_API_KEY` — optional; enables voice transcription via `gpt-4o-mini-transcribe`
- `DATA_DIR` — defaults to `./data`
