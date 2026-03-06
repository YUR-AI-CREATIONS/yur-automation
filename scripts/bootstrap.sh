#!/bin/bash
# FranklinOps — All-in-One Bootstrap (Mac/Linux)
# One script. Installs what's missing. Runs.

set -e
cd "$(dirname "$0")/.."

echo ""
echo "  FRANKLINOPS — All-in-One Bootstrap"
echo ""

# Python
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
if [ -z "$PY" ]; then
    echo "  Python not found. Install from python.org or: brew install python3"
    exit 1
fi

# Ollama (optional)
if ! command -v ollama &>/dev/null; then
    echo "  Install Ollama for AI: https://ollama.com"
fi

# Deps
$PY -m pip install -r requirements-minimal.txt -q 2>/dev/null

# Model (background)
command -v ollama &>/dev/null && (ollama pull llama3 &) 2>/dev/null || true

# Run
echo "  Starting... Browser opens in 3s."
echo ""
(sleep 3; (open http://127.0.0.1:8844/ui/boot 2>/dev/null || xdg-open http://127.0.0.1:8844/ui/boot 2>/dev/null || true)) &
$PY -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
