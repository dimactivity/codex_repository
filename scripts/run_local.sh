#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .venv ]; then
  echo "[ERROR] .venv not found. Run ./scripts/bootstrap.sh first."
  exit 1
fi

source .venv/bin/activate

if [ ! -f .env ]; then
  echo "[ERROR] .env not found. Copy .env.example to .env and fill TELEGRAM_BOT_TOKEN."
  exit 1
fi

if ! grep -q '^TELEGRAM_BOT_TOKEN=' .env; then
  echo "[ERROR] TELEGRAM_BOT_TOKEN key missing in .env"
  exit 1
fi

TOKEN_VALUE="$(grep '^TELEGRAM_BOT_TOKEN=' .env | head -n1 | cut -d'=' -f2-)"
if [ -z "${TOKEN_VALUE}" ]; then
  echo "[ERROR] TELEGRAM_BOT_TOKEN is empty in .env"
  exit 1
fi

python src/digital_brain_bot.py
