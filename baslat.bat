@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >/dev/null 2>/dev/null || (echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle. & pause & exit /b 1)
python araclar\emulator.py baglan || echo Emulator baglanamadi. Emulatoru acip baslat.bat i tekrar calistir.
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8881/panel"
echo.
echo Sunucu calisiyor. Oyunu emulatorde ac. Kapatmak icin bu pencereyi kapat.
python sunucu\sunucu.py
pause
