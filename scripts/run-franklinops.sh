#!/bin/bash
# FranklinOps — Red Carpet Experience
# Documents in. Decisions out. Humans in control.

set -e
cd "$(dirname "$0")/.."

echo ""
echo "  ============================================================"
echo "   FRANKLINOPS — Red Carpet Experience"
echo "   Documents in. Decisions out. Humans in control."
echo "  ============================================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found. Install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi
PYTHON=$(command -v python3 2>/dev/null || command -v python)

# Check dependencies
if ! $PYTHON -c "import uvicorn" 2>/dev/null; then
    echo "[SETUP] Installing dependencies (first run only)..."
    $PYTHON -m pip install -r requirements-minimal.txt -q
    echo "[OK] Dependencies installed."
    echo ""
fi

echo "[START] Launching FranklinOps..."
echo ""
echo "  Opening browser in 3 seconds..."
echo "    http://127.0.0.1:8844/ui/boot"
echo ""
echo "  Press Ctrl+C to stop the server."
echo "  ============================================================"
echo ""

# Open browser after short delay (macOS, Linux)
(sleep 3 && (open http://127.0.0.1:8844/ui/boot 2>/dev/null || xdg-open http://127.0.0.1:8844/ui/boot 2>/dev/null || true)) &
$PYTHON -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
