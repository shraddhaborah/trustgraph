#!/usr/bin/env bash
# Runs each time you attach. Starts everything in the background.
export PATH="$HOME/.temporalio/bin:$PATH"
cd "$(dirname "$0")/.."

pgrep -f "temporal server start-dev" >/dev/null || \
  (temporal server start-dev >/tmp/temporal.log 2>&1 &)
sleep 5

cd backend
pgrep -f "python worker.py" >/dev/null || \
  (./venv/bin/python worker.py >/tmp/worker.log 2>&1 &)
pgrep -f "uvicorn main:app" >/dev/null || \
  (./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 >/tmp/api.log 2>&1 &)

cd ../frontend
pgrep -f "vite" >/dev/null || (npm run dev >/tmp/vite.log 2>&1 &)

sleep 3
echo ""
echo "  TrustGraph is running. Open the forwarded port 5173 and upload a PDF."
echo "  Running in DEMO_MODE — add ANTHROPIC_API_KEY to backend/.env for real extraction."
echo ""
