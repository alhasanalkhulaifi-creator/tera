#!/usr/bin/env bash
# Multi-worker + uvloop + httptools. Tune workers to CPU cores.
set -euo pipefail
cd "$(dirname "$0")/.."
export UVICORN_WORKERS="${UVICORN_WORKERS:-4}"
exec ./venv/bin/python -m uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS}" \
  --loop uvloop \
  --http httptools \
  --log-level info
