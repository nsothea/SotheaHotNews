@echo off
title Allow Sothea Hot News on Home Network (Port 5000)
cd /d "%~dp0"

echo ====================================================================
echo   កំពុងបើកសិទ្ធិ Port 5000 និងប្តូរ Network លើ Windows Defender Firewall...
echo ====================================================================
echo.

:: 1. Add Inbound Firewall rule for Port 5000 TCP & UDP
netsh advfirewall firewall delete rule name="Sothea Hot News (Port 5000)" >nul 2>&1
netsh advfirewall firewall add rule name="Sothea Hot News (Port 5000)" dir=in action=allow protocol=TCP localport=5000 profile=any >nul 2>&1
netsh advfirewall firewall add rule name="Sothea Hot News (Port 5000 UDP)" dir=in action=allow protocol=UDP localport=5000 profile=any >nul 2>&1

:: 2. Add rule for Python executable directly
netsh advfirewall firewall delete rule name="Sothea Hot News Python" >nul 2>&1
netsh advfirewall firewall add rule name="Sothea Hot News Python" dir=in action=allow program="%~dp0.venv\Scripts\python.exe" profile=any >nul 2>&1

:: 3. Switch Ethernet network category to Private so Windows allows LAN discovery
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-NetConnectionProfile -InterfaceAlias 'Ethernet' -NetworkCategory Private -ErrorAction SilentlyContinue" >nul 2>&1

echo ====================================================================
echo   [ជោគជ័យ] បានបើក Port 5000 និងប្តូរ Network ទៅជា Private រួចរាល់!
echo.
echo   [ចំណុចសំខាន់ដើម្បីបើកចេញលើទូរស័ព្ទដៃ]៖
echo   1. ត្រូវប្រាកដថាទូរស័ព្ទបានបិទ 4G/5G ហើយភ្ជាប់ Wifi ផ្ទះជាមួយគ្នា
echo   2. នៅលើ Browser ទូរស័ព្ទ (Chrome/Safari) ត្រូវវាយ http:// ពេញលេញ៖
echo      http://192.168.1.117:5000
echo      (ហាមវាយ https:// ព្រោះប្រព័ន្ធដំណើរការលើ http://)
echo ====================================================================
echo.
pause
