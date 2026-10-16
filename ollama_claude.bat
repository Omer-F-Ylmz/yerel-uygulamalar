@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Ollama ile calisan Claude Code: ayri profil (.claude-ollama), model menusu
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-ollama"
if not exist "%CLAUDE_CONFIG_DIR%\skills" mkdir "%CLAUDE_CONFIG_DIR%\skills"
where ollama >nul 2>nul || (echo Ollama bulunamadi. https://ollama.com/download adresinden kur. & pause & exit /b 1)
echo ===== Model sec =====
echo  1. glm-5.3          (varsayilan - kod ve ajan islerinde en guclu)
echo  2. kimi-k3          (cok yetenekli, gorsel de okur)
echo  3. deepseek-v4-pro  (uc dusunme modu)
echo  4. kimi-k2.7-code   (sadece kod, hizli)
echo  5. minimax-m3       (hafif ve hizli)
echo  6. gemma4:31b       (eski model)
echo.
set "S="
set /p S=Secim (bos birakip Enter = glm-5.3): 
set "MODEL=glm-5.3"
if "%S%"=="2" set "MODEL=kimi-k3"
if "%S%"=="3" set "MODEL=deepseek-v4-pro"
if "%S%"=="4" set "MODEL=kimi-k2.7-code"
if "%S%"=="5" set "MODEL=minimax-m3"
if "%S%"=="6" set "MODEL=gemma4:31b"
rem Bulut etiketini dene; Ollama tanimiyorsa duz adi kullan
echo %MODEL% | find ":" >nul || (ollama show %MODEL%:cloud >nul 2>nul && set "MODEL=%MODEL%:cloud")
echo.
echo Model: %MODEL%
echo.
ollama launch claude --model %MODEL%
pause
