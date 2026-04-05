#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Install Python 3.11+ first."
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[INFO] Created .env from .env.example"
else
  echo "[INFO] .env already exists"
fi

echo "[OK] Bootstrap complete. Next: edit .env and run ./scripts/run_local.sh"
