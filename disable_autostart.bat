@echo off
title Disable Sothea Hot News Auto-Start
cd /d "%~dp0"

set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SotheaHotNews.vbs"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [OK] Sothea Hot News Auto-Start has been disabled.
) else (
    echo [*] Auto-Start was not enabled.
)

pause
