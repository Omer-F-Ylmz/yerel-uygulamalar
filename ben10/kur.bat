@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Ben 10: Battle Ready bir Shockwave (Adobe Director) oyunu; Flash degil, Ruffle acamaz.
rem Flashpoint arsivinde "Oynanabilir" kayitli: Flashpoint Infinity + CLIFp ile tek tikla aciyoruz.
set "HEDEF=%USERPROFILE%\Flashpoint"
set "INDIR=%~dp0indir"
set "FP_URL=https://download.unstable.life/archive/infinity/Flashpoint%%20Infinity%%2014.0.3.7z"
set "CLIFP_URL=https://github.com/oblivioncth/CLIFp/releases/download/v0.9.16/CLIFp_v0.9.16_Windows_Static_x64.zip"
set "SEVENZR_URL=https://www.7-zip.org/a/7zr.exe"
where curl >nul 2>nul || (echo curl bulunamadi. Windows 10 veya 11 gerekir. & pause & exit /b 1)
if not exist "%INDIR%" mkdir "%INDIR%"

call :kok_bul
if defined KOK (
  echo Flashpoint zaten kurulu: %KOK%
  goto clifp
)

echo [1/4] Flashpoint Infinity 14.0.3 indiriliyor (1.1 GB, bir kez; diskte ~5 GB bos yer gerekir)...
if not exist "%INDIR%\fp.7z" (
  curl -L --fail -o "%INDIR%\fp.7z.part" "%FP_URL%" || (echo Indirme basarisiz. Internetini kontrol edip tekrar dene. & pause & exit /b 1)
  move /y "%INDIR%\fp.7z.part" "%INDIR%\fp.7z" >nul
)
if not exist "%INDIR%\7zr.exe" curl -L --fail -o "%INDIR%\7zr.exe" "%SEVENZR_URL%" || (echo 7-Zip indirilemedi. & pause & exit /b 1)

echo [2/4] Aciliyor: %HEDEF%  (birkac dakika surer)
echo       Antivirus uyari verirse bu klasoru izinli listesine ekle; Flashpoint bilinen bir yanlis alarm.
"%INDIR%\7zr.exe" x "%INDIR%\fp.7z" -o"%HEDEF%" -y >nul || (echo Arsiv acilamadi. & pause & exit /b 1)
del "%INDIR%\fp.7z"
call :kok_bul
if not defined KOK (echo Flashpoint klasoru bulunamadi: %HEDEF% & pause & exit /b 1)

:clifp
if exist "%KOK%CLIFp.exe" goto ilk_acilis
echo [3/4] CLIFp (Flashpoint oyunlarini tek komutla acan arac) indiriliyor...
curl -L --fail -o "%INDIR%\clifp.zip" "%CLIFP_URL%" || (echo CLIFp indirilemedi. & pause & exit /b 1)
if exist "%INDIR%\clifp" rmdir /s /q "%INDIR%\clifp"
mkdir "%INDIR%\clifp"
tar -xf "%INDIR%\clifp.zip" -C "%INDIR%\clifp" || (echo CLIFp acilamadi. & pause & exit /b 1)
for /f "delims=" %%F in ('dir /s /b "%INDIR%\clifp\CLIFp.exe" 2^>nul') do copy /y "%%F" "%KOK%CLIFp.exe" >nul
if not exist "%KOK%CLIFp.exe" (echo CLIFp.exe bulunamadi. & pause & exit /b 1)

:ilk_acilis
echo %KOK%> "%~dp0fp_yolu.txt"
rem Onceki surum Flashpoint'i yanlis klasorden acip proje klasorune preferences.json yaziyordu
if exist "%~dp0..\preferences.json" del "%~dp0..\preferences.json"
if exist "%~dp0ilk_acilis_tamam2" goto bitti
echo [4/4] Flashpoint bir kez kendi penceresiyle acilacak (gerekli).
echo       Acilip oyun listesi yuklenince pencereyi KAPAT; kurulum kendiliginden biter.
rem Flashpoint yollari calisma klasorune gore cozuyor: Launcher klasorunden acilmali
start "" /D "%KOK%Launcher" /wait "%KOK%Launcher\Flashpoint.exe"
echo.> "%~dp0ilk_acilis_tamam2"

:bitti
echo.
echo Kurulum tamam. Oynamak icin: ben10\oyna.bat
pause
exit /b 0

:kok_bul
rem Arsivin kokunde Launcher\, FPSoftware\, Data\ klasorleri var
set "KOK="
if exist "%HEDEF%\Launcher\Flashpoint.exe" set "KOK=%HEDEF%\"
exit /b 0
