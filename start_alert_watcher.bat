@echo off
title War News Desktop Alert Watcher
cd /d "%~dp0"
echo =========================================================
echo   War News Desktop Alert Watcher is starting...
echo   - Windows Desktop Toast Notifications: ENABLED
echo   - Audio Sound Alerts: ENABLED
echo   - Telegram / Discord Alerts: (See .env)
echo =========================================================
echo.
call .venv\Scripts\python.exe alert_watcher.py
pause
