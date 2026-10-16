@echo off
cd /d "%~dp0"
rem Tokyo Ghoul APK'larini indirtir, parcalayip Claude'a gonderir
powershell -NoProfile -ExecutionPolicy Bypass -File araclar\tg_indir.ps1 || goto hata
echo Dosyalar parcalaniyor...
powershell -NoProfile -ExecutionPolicy Bypass -File araclar\dosya_parcala.ps1 tokyo_ghoul tokyo_ghoul_parca || goto hata
git add -f tokyo_ghoul_parca || goto hata
git commit -m "Tokyo Ghoul APK parcalari eklendi" || goto hata
echo Gonderiliyor, birkac dakika surebilir...
git pull --no-rebase --no-edit >nul 2>nul
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
