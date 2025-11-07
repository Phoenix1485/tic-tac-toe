@echo off
setlocal

:: Lokale IP-Adresse ermitteln
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4-Adresse"') do set IP=%%a
set IP=%IP:~1%

echo ========================================
echo Deine lokale IP-Adresse: %IP%
echo Backend erreichbar unter: http://%IP%:8000
echo Frontend erreichbar unter: http://%IP%:5500
echo ========================================

:: Backend starten (FastAPI mit uvicorn im venv)
start cmd /k "cd /d \"C:\Users\R326215\OneDrive - methylmethacrylate\Documents\Projekte\codes\langeweile\TicTacToe\" && call \"venv\\Scripts\\activate.bat\" && python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload"

:: Frontend starten (Python HTTP Server)
start cmd /k "cd /d \"C:\Users\R326215\OneDrive - methylmethacrylate\Documents\Projekte\codes\langeweile\TicTacToe\\frontend\" && python -m http.server 5500"

endlocal