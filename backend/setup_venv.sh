#!/usr/bin/env bash
# POSIX helper to create a Python 3.12 virtualenv (if python3.12 is available)
set -euo pipefail

if command -v python3.12 >/dev/null 2>&1; then
  PY=python3.12
elif command -v py >/dev/null 2>&1 && py -3.12 -c 'import sys' >/dev/null 2>&1; then
  PY="py -3.12"
else
  echo "Python 3.12 not found. Please install Python 3.12 and retry." >&2
  exit 1
fi

VENV_DIR="backend/.venv"
if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi

"Activating venv and installing requirements..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r backend/requirements.txt

echo "Done. Activate with: source $VENV_DIR/bin/activate"
