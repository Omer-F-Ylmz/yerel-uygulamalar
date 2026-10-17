@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
echo Oyun takildigi ekranda acik kalsin. Kayit aliniyor...
%PY% araclar\emulator.py kayit || (pause & exit /b 1)
rem Sunucu gunlugu ve mac izleri de gitsin (kayit.json, yani oyun kaydin GITMEZ)
if not exist teshis_paket mkdir teshis_paket
for %%F in (sunucu.log mac_izi.txt istemci_hatalari.txt) do if exist "sunucu\kayit\%%F" copy /y "sunucu\kayit\%%F" "teshis_paket\%%F" >nul
git add -f teshis.txt teshis_paket
git commit -m "Anlik kayit" >nul
git pull --no-rebase --no-edit >nul 2>nul
git push || (echo Gonderilemedi, ekran goruntusu at. & pause & exit /b 1)
echo.
echo TAMAM. Claude a "kayit gonderdim" yaz.
pause
