@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
%PY% araclar\emulator.py baglan || echo Emulator baglanamadi. Emulatoru acip baslat.bat i tekrar calistir.
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8881/panel"
echo.
echo Sunucu calisiyor. Oyunu emulatorde ac. Kapatmak icin bu pencereyi kapat.
%PY% sunucu\sunucu.py
pause
