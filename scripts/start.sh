#!/usr/bin/env bash
# Linux counterpart of start.ps1. The Windows desktop window (WebView2) is not available here,
# so this starts the local server in browser mode and prints the address.
#   bash scripts/start.sh            # stop with Ctrl+C
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
[ -d "$VENV" ] || { echo "Virtual environment not found. Run: bash scripts/setup.sh" >&2; exit 1; }

PYTHON="$VENV/bin/python"
[ -x "$PYTHON" ] || { echo "Python runtime was not found in .venv. Run: bash scripts/setup.sh" >&2; exit 1; }

cd "$ROOT"
exec "$PYTHON" -X utf8 run.py --browser "$@"
