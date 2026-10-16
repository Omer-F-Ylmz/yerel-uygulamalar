@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
echo Oyun takildigi ekranda acik kalsin. Kayit aliniyor...
%PY% araclar\emulator.py kayit || (pause & exit /b 1)
git add -f teshis.txt
git commit -m "Anlik kayit" >nul
git push || (echo Gonderilemedi, ekran goruntusu at. & pause & exit /b 1)
echo.
echo TAMAM. Claude a "kayit gonderdim" yaz.
pause
