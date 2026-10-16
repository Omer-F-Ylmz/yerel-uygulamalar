@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >/dev/null 2>/dev/null || (echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle. & pause & exit /b 1)
echo Emulator acik olmali. Kurulum basliyor...
python araclar\emulator.py kur
pause
