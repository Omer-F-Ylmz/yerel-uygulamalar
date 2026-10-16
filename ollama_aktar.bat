@echo off
chcp 65001 >nul
cd /d "%~dp0"
call araclar\python_bul.bat || (pause & exit /b 1)
:menu
cls
echo ===== Ollama profiline aktarma =====
echo.
%PY% araclar\ollama_profil.py durum
echo.
echo  1. Her seyi aktar (skill, ajan, komut, eklenti, MCP)
echo  2. MCP sunucularindan sec
echo  3. Skill sec (skill_ekle.bat)
echo  4. Hafif mod: eklenti, hook ve MCP kapat ("Prompt is too long" hatasi icin)
echo  5. Ollama profilini temizle (fazla geldiyse)
echo  6. Cikis
echo.
set "S="
set /p S=Secimin: 
if "%S%"=="1" %PY% araclar\ollama_profil.py hepsi & pause & goto menu
if "%S%"=="2" %PY% araclar\ollama_profil.py mcp & pause & goto menu
if "%S%"=="3" call skill_ekle.bat & goto menu
if "%S%"=="4" %PY% araclar\ollama_profil.py hafif & pause & goto menu
if "%S%"=="5" %PY% araclar\ollama_profil.py sifirla & pause & goto menu
if "%S%"=="6" exit /b 0
goto menu
