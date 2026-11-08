@echo off
chcp 65001 >nul
title Auto-Sync to D:\SotheaHotNews_Upload
echo ========================================================
echo   SYNCING FILES TO D:\SotheaHotNews_Upload
echo ========================================================
echo.
.venv\Scripts\python.exe sync_upload_folder.py
echo.
echo ========================================================
echo   Done! Folder D:\SotheaHotNews_Upload is 100%% up to date!
echo ========================================================
pause
