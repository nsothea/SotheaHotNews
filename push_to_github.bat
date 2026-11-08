@echo off
chcp 65001 >nul
title Upload SotheaHotNews to GitHub
echo ========================================================
echo   SOTHEA HOT NEWS - UPLOADING CODE TO GITHUB...
echo ========================================================
echo.
cd /d "D:\AI_Project\News"
"C:\Program Files\Git\cmd\git.exe" add admin_service.py app.py site_settings.json templates/index.html uploads/site_logo.png uploads/site_logo_256.png tts_service.py news_database.json .gitignore push_to_github.bat
"C:\Program Files\Git\cmd\git.exe" commit -m "Fix mobile loading hang: Stale-While-Revalidate caching and pre-warmed news DB"
"C:\Program Files\Git\cmd\git.exe" push -u origin main
echo.
if %errorlevel% equ 0 (
    echo ========================================================
    echo   [SUCCESS] Upload to GitHub Successful!
    echo ========================================================
) else (
    echo ========================================================
    echo   Please check your browser to Authorize / Sign In.
    echo ========================================================
)
echo.
pause
