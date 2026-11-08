@echo off
setlocal
title Configure sotheahotnews.com Domain

:: Check for Administrator permissions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Requesting Administrator privileges to update Windows hosts file...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"\"%~dpnx0\"\"' -Verb RunAs"
    exit /b
)

echo ========================================================
echo   Configuring sotheahotnews.com in Windows Hosts File
echo ========================================================
echo.

set HOSTS=%WINDIR%\System32\drivers\etc\hosts

:: Check if already present
findstr /C:"sotheahotnews.com" "%HOSTS%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] sotheahotnews.com is ALREADY configured in your hosts file!
) else (
    echo 127.0.0.1 sotheahotnews.com>> "%HOSTS%"
    echo 127.0.0.1 www.sotheahotnews.com>> "%HOSTS%"
    echo 127.0.0.1 sotheanews.info>> "%HOSTS%"
    echo 127.0.0.1 www.sotheanews.info>> "%HOSTS%"
    echo [SUCCESS] Successfully added sotheahotnews.com to your Windows hosts file!
)

ipconfig /flushdns >nul 2>&1

echo.
echo ========================================================
echo   DONE! You can now open in your browser:
echo   http://sotheahotnews.com:5000
echo ========================================================
echo.
pause
