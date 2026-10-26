#!/usr/bin/env bash
# One-command launcher for macOS / Linux
set -e
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
streamlit run app.py
