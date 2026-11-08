@echo off
title Sothea Hot News - Web Portal & Notification Watcher
cd /d "%~dp0"

echo =========================================================
echo   SOTHEA HOT NEWS - Web Portal & Notification Watcher
echo   - លើកុំព្យូទ័រផ្ទាល់ (Local PC) : http://localhost:5000
echo   - លើទូរស័ព្ទដៃតាម Wifi ផ្ទះ    : http://192.168.1.117:5000
echo   - ប្រព័ន្ធ Cloudflare Mobile HTTPS Tunnel : បើកស្វ័យប្រវត្ត (ACTIVE)
echo   - ប្រព័ន្ធ Desktop Toast Notification    : សកម្មស្វ័យប្រវត្ត (ACTIVE)
echo   - ការជូនដំណឹងលើ Browser                : សកម្ម (ACTIVE)
echo =========================================================
echo.

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:5000"

:: Start the Flask Web Application & Integrated Notification Watcher
call .venv\Scripts\python.exe app.py
pause
