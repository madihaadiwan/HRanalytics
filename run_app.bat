@echo off
REM One-command launcher for Windows
cd /d "%~dp0"
if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
streamlit run app.py
