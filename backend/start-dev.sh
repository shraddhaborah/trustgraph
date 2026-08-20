#!/usr/bin/env bash
# Starts all three processes. Run from backend/:  ./start-dev.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "Missing .env -- copy .env.example to .env and add your key."; exit 1; }

pgrep -f "temporal server start-dev" >/dev/null || {
  echo "Starting Temporal dev server..."
  temporal server start-dev >/tmp/temporal.log 2>&1 &
  sleep 5
}

echo "Starting worker..."
python worker.py >/tmp/worker.log 2>&1 &
WORKER_PID=$!

fuser -k 8000/tcp 2>/dev/null || true
sleep 1
echo "Starting API on :8000 (worker pid $WORKER_PID; logs in /tmp/worker.log)"
trap "kill $WORKER_PID 2>/dev/null || true" EXIT
uvicorn main:app --reload --host 0.0.0.0 --port 8000
