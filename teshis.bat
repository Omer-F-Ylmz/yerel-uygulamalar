@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
echo Emulator acik olmali, baslat.bat penceresi de acik kalsin.
%PY% araclar\emulator.py teshis || (pause & exit /b 1)
git add -f teshis.txt
git commit -m "Teshis kaydi" >nul
git pull --no-edit >nul 2>nul
git push || (echo Gonderilemedi, ekran goruntusu at. & pause & exit /b 1)
echo.
echo TAMAM. Claude a "teshis gonderdim" yaz.
pause
