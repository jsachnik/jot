#!/bin/sh
# Start Jot on macOS / Linux:  ./run.sh
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting things up (one time)..."
  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
.venv/bin/python app.py
