@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
echo Emulator acik olmali. Kurulum basliyor...
%PY% araclar\emulator.py kur
pause
