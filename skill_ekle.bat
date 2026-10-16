@echo off
chcp 65001 >nul
set "ESKI=%USERPROFILE%\.claude\skills"
set "YENI=%USERPROFILE%\.claude-ollama\skills"
if not exist "%YENI%" mkdir "%YENI%"
echo === Eski kurulumdaki skilller ===
dir /b "%ESKI%"
echo.
echo === Ollama profilinde olanlar ===
dir /b "%YENI%"
echo.
:sor
set "AD="
set /p AD=Eklenecek skill adi (bitirmek icin bos birakip Enter): 
if "%AD%"=="" goto son
if exist "%ESKI%\%AD%\SKILL.md" (
    xcopy /e /i /y "%ESKI%\%AD%" "%YENI%\%AD%" >nul
    echo Eklendi: %AD%
) else (
    echo Bulunamadi: %AD%  ^(adi listedeki gibi yaz^)
)
goto sor
:son
echo.
echo Bitti. Claude Code u kapatip ollama_claude.bat ile yeniden ac.
pause
