@echo off
REM Backend für TicTacToe starten
REM Stelle sicher, dass FastAPI und Uvicorn installiert sind:
REM pip install fastapi uvicorn

echo Starte Backend auf http://localhost:8000 ...
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause