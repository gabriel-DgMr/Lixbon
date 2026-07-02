@echo off
:: Inicia el Gateway FOLAX DTC
cd /d "%~dp0"
set PYTHONPATH=%~dp0
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

