@echo off
cd /d "%~dp0"
echo OBB parcalaniyor...
powershell -NoProfile -ExecutionPolicy Bypass -File araclar\obb_parcala.ps1 || goto hata
git add -f obb_parca || goto hata
git commit -m "OBB parcalari eklendi" || goto hata
echo Gonderiliyor, birkac dakika surebilir...
git pull --no-edit >nul 2>nul
git pull --no-edit >nul 2>nul
git push || goto hata
echo.
echo TAMAM. Claude a "gonderdim" yaz.
pause
exit /b 0
:hata
echo.
echo Bir hata oldu, bu pencerenin ekran goruntusunu Claude a gonder.
pause
exit /b 1
