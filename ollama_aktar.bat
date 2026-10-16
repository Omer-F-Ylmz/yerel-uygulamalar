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
echo  4. Onar: "Prompt is too long" ve hookify hatasi (hicbir seyi kapatmaz)
echo  5. claude-mem hafizasini ucretsiz Gemini anahtarina gecir
echo  6. MCP baglanti testi
echo  7. Ollama profilini temizle
echo  8. Cikis
echo.
set "S="
set /p S=Secimin: 
if "%S%"=="1" %PY% araclar\ollama_profil.py hepsi & pause & goto menu
if "%S%"=="2" %PY% araclar\ollama_profil.py mcp & pause & goto menu
if "%S%"=="3" call skill_ekle.bat & goto menu
if "%S%"=="4" %PY% araclar\ollama_profil.py onar & pause & goto menu
if "%S%"=="5" %PY% araclar\ollama_profil.py hafiza & pause & goto menu
if "%S%"=="6" %PY% araclar\ollama_profil.py kapi & pause & goto menu
if "%S%"=="7" %PY% araclar\ollama_profil.py sifirla & pause & goto menu
if "%S%"=="8" exit /b 0
goto menu
