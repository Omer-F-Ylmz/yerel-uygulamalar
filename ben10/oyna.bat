@echo off
chcp 65001 >nul
rem Flashpoint kaydi: "Ben 10: Battle Ready" (Shockwave, This Is Pop / Cartoon Network, 2006)
set "OYUN_ID=dbb21635-b0d5-78d9-a749-c4778a07e698"
if not exist "%~dp0fp_yolu.txt" (echo Once ben10\kur.bat'i calistir. & pause & exit /b 1)
if not exist "%~dp0ilk_acilis_tamam2" call "%~dp0kur.bat"
set /p KOK=<"%~dp0fp_yolu.txt"
if not exist "%KOK%CLIFp.exe" (echo Flashpoint kurulumu bozulmus; ben10\kur.bat'i tekrar calistir. & pause & exit /b 1)
rem Acik Flashpoint penceresi kendi sunucusunu tutar ve CLIFp'nin sunucusuyla cakisir
tasklist /fi "imagename eq Flashpoint.exe" | find /i "Flashpoint.exe" >nul && (
  echo Flashpoint penceresi acik; once onu kapat, sonra tekrar dene.
  pause
  exit /b 1
)
echo Ben 10: Battle Ready aciliyor... (ilk seferde oyun dosyasi indirilir)
cd /d "%KOK%"
"%KOK%CLIFp.exe" play -i %OYUN_ID% && exit /b 0
echo.
echo Hizli baslatma calismadi. Flashpoint penceresi aciliyor:
echo   ust taraftaki arama kutusuna "Battle Ready" yaz, oyuna cift tikla.
start "" /D "%KOK%Launcher" "%KOK%Launcher\Flashpoint.exe"
