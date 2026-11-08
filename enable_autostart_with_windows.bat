@echo off
title Enable Sothea Hot News Auto-Start with Windows
cd /d "%~dp0"

echo ========================================================
echo   Setting up Sothea Hot News to start with Windows...
echo ========================================================
echo.

set "TARGET=%~dp0run_silent.vbs"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SotheaHotNews.vbs"

copy /y "%TARGET%" "%SHORTCUT%" >nul

if %errorlevel% equ 0 (
    echo [OK] Auto-Start enabled successfully!
    echo.
    echo ចាប់ពីពេលនេះទៅ រាល់ពេលលោកអ្នកបើកកុំព្យូទ័រ Server នឹងដំណើរការស្ងាត់ៗក្នុង Background ដោយស្វ័យប្រវត្តិ។
    echo លោកអ្នកគ្រាន់តែបើក Browser វាយ http://127.0.0.1:5000 គឺដើរភ្លាម ដោយមិនបាច់ចុច start_website.bat ទៀតឡើយ!
) else (
    echo [!] Failed to copy startup file.
)

echo.
pause
