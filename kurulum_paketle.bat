@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
%PY% araclar\kurulum_paketle.py
echo.
echo Masaustundeki claude-kurulum-paketi klasorundeki RAPOR.txt yi oku, sonra Claude a haber ver.
pause
