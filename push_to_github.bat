@echo off
chcp 65001 >nul
title Upload SotheaHotNews to GitHub
echo ========================================================
echo   SOTHEA HOT NEWS - UPLOADING CODE TO GITHUB...
echo ========================================================
echo.
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
