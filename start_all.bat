@echo off
chcp 65001 >nul
echo ========================================
echo   TeX Agent - Start Both Servers
echo ========================================
echo.

echo [1/4] Cleaning up old processes...
for /f "tokens=5" %%i in ('netstat -ano ^| findstr ":8765 " ^| findstr LISTENING') do taskkill /F /PID %%i >nul 2>&1
for /f "tokens=5" %%i in ('netstat -ano ^| findstr ":8772 " ^| findstr LISTENING') do taskkill /F /PID %%i >nul 2>&1
echo        Done.
echo.

echo [2/4] Starting Chat Mode (port 8765)...
start "TeX Agent - Chat" cmd /c "C:\Users\junta\miniconda3\envs\agent\python.exe -m ui.web.server"
echo.

echo [3/4] Starting Writing Mode (port 8772)...
start "TeX Agent - Overleaf" cmd /c "C:\Users\junta\miniconda3\envs\agent\python.exe -m ui.overleaf.server"
echo.

echo [4/4] Both servers are starting...
echo.
echo   Chat Mode:    http://127.0.0.1:8765/
echo   Writing Mode: http://127.0.0.1:8772/
echo.
echo Close the server windows to stop.
pause
