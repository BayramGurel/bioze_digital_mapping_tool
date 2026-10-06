@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Maak eerst de omgeving volgens README.md.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m streamlit run Home.py
