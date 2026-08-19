#!/usr/bin/env bash
# Runs once when the Codespace is created.
set -e
echo "→ Installing Temporal CLI"
curl -sSf https://temporal.download/cli.sh | sh
echo 'export PATH="$HOME/.temporalio/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.temporalio/bin:$PATH"

echo "→ Python deps"
cd backend
python -m venv venv
./venv/bin/pip install -q -r requirements.txt

# Demo mode by default: no API key needed to see the pipeline work.
[ -f .env ] || printf 'DEMO_MODE=true\n' > .env

echo "→ Node deps"
cd ../frontend
npm install --silent

echo "✓ Setup complete"
