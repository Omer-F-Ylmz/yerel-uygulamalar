@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Flashpoint kaydi: "Ben 10: Battle Ready" (Shockwave, This Is Pop / Cartoon Network, 2006)
set "OYUN_ID=dbb21635-b0d5-78d9-a749-c4778a07e698"
if not exist "%~dp0fp_yolu.txt" (echo Once ben10\kur.bat'i calistir. & pause & exit /b 1)
set /p KOK=<"%~dp0fp_yolu.txt"
if not exist "%KOK%CLIFp.exe" (echo Flashpoint kurulumu bozulmus; ben10\kur.bat'i tekrar calistir. & pause & exit /b 1)
echo Ben 10: Battle Ready aciliyor... (ilk seferde oyun dosyasi indirilir)
"%KOK%CLIFp.exe" play -i %OYUN_ID%
