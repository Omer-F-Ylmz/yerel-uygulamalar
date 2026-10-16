@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Ollama ile calisan Claude Code: ayri profil (.claude-ollama), UCRETSIZ model menusu
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-ollama"
if not exist "%CLAUDE_CONFIG_DIR%\skills" mkdir "%CLAUDE_CONFIG_DIR%\skills"
where ollama >nul 2>nul || (echo Ollama bulunamadi. https://ollama.com/download adresinden kur. & pause & exit /b 1)
:menu
echo ===== Ucretsiz model sec =====
echo  -- Bulut: bilgisayarin bellegini HIC kullanmaz, baska islerle rahat calisir --
echo  1. nemotron-3-ultra:cloud  (varsayilan - bedava olanlarin en gucludu)
echo  2. gemma4:31b-cloud        (bedava oldugu kesin)
echo  3. gpt-oss:120b-cloud      (yedek)
echo  -- Yerel: sinirsiz ve internetsiz, ekran kartini kullanir --
echo  4. qwen3.5:9b              (hafif, ~8-10 GB ekran karti, arka planda rahat)
echo  5. qwen3.6:35b             (en guclu yerel ama agir, RAM'e de tasar)
echo  6. gpt-oss:20b             (orta)
echo  -- Diger --
echo  7. OpenRouter bedava modelleri (ucretsiz anahtar gerekir)
echo  T. Bulut modelleri test et (hangisi bedava calisiyor?)
echo.
set "S="
set /p S=Secim (bos birakip Enter = 1): 
set "MODEL=nemotron-3-ultra:cloud"
set "YEREL="
if "%S%"=="2" set "MODEL=gemma4:31b-cloud"
if "%S%"=="3" set "MODEL=gpt-oss:120b-cloud"
if "%S%"=="4" (set "MODEL=qwen3.5:9b" & set "YEREL=1")
if "%S%"=="5" (set "MODEL=qwen3.6:35b" & set "YEREL=1")
if "%S%"=="6" (set "MODEL=gpt-oss:20b" & set "YEREL=1")
if "%S%"=="7" goto openrouter
if /i "%S%"=="T" goto test
rem Claude Code bu modelleri tanimiyor, baglami 200K saniyor; gercek pencereyi bildir
set "CTX=262144"
if "%MODEL%"=="gpt-oss:120b-cloud" set "CTX=131072"
if defined YEREL set "CTX=65536"
set "CLAUDE_CODE_MAX_CONTEXT_TOKENS=%CTX%"
if defined YEREL (
  if not defined OLLAMA_CONTEXT_LENGTH echo [Ipucu] Bellek ayarlari yapilmamis. Once ollama_ayar.bat'i bir kez calistir.
  ollama list | find /i "%MODEL%" >nul || (echo %MODEL% indiriliyor, bir kez yapilir... & ollama pull %MODEL%)
)
echo.
echo Model: %MODEL%
echo (402 hatasi alirsan bu model ucretli olmus demektir: menuden baska model sec.)
echo.
ollama launch claude --model %MODEL%
pause
exit /b

:test
echo.
for %%M in (nemotron-3-ultra:cloud gemma4:31b-cloud gpt-oss:120b-cloud) do (
  ollama run %%M "Sadece OK yaz" >nul 2>nul && echo   BEDAVA CALISIYOR : %%M || echo   CALISMIYOR/UCRETLI: %%M
)
echo.
goto menu

:openrouter
rem OpenRouter'in Anthropic uyumlu adresi; anahtar https://openrouter.ai/keys adresinden ucretsiz alinir
if not defined OPENROUTER_API_KEY (
  echo OpenRouter anahtari bulunamadi. https://openrouter.ai/keys adresinden ucretsiz al.
  set /p OPENROUTER_API_KEY=Anahtari yapistir: 
)
if not defined OPENROUTER_API_KEY (echo Anahtar girilmedi. & pause & exit /b 1)
setx OPENROUTER_API_KEY "%OPENROUTER_API_KEY%" >nul
echo.
echo  1. nvidia/nemotron-3-ultra-550b-a55b:free  (varsayilan)
echo  2. poolside/laguna-s-2.1:free
echo  3. nvidia/nemotron-3-super-120b-a12b:free
echo  4. google/gemma-4-31b-it:free
set "S="
set /p S=Secim (bos = 1): 
set "ORMODEL=nvidia/nemotron-3-ultra-550b-a55b:free"
if "%S%"=="2" set "ORMODEL=poolside/laguna-s-2.1:free"
if "%S%"=="3" set "ORMODEL=nvidia/nemotron-3-super-120b-a12b:free"
if "%S%"=="4" set "ORMODEL=google/gemma-4-31b-it:free"
set "CLAUDE_CODE_MAX_CONTEXT_TOKENS=262144"
if "%S%"=="2" set "CLAUDE_CODE_MAX_CONTEXT_TOKENS=131072"
if "%S%"=="3" set "CLAUDE_CODE_MAX_CONTEXT_TOKENS=131072"
set "ANTHROPIC_BASE_URL=https://openrouter.ai/api"
set "ANTHROPIC_AUTH_TOKEN=%OPENROUTER_API_KEY%"
set "ANTHROPIC_API_KEY="
set "ANTHROPIC_MODEL=%ORMODEL%"
rem Arka plan islerinde de ayni bedava model kullanilsin (yoksa ucretli Claude modelini ister)
set "ANTHROPIC_DEFAULT_OPUS_MODEL=%ORMODEL%"
set "ANTHROPIC_DEFAULT_SONNET_MODEL=%ORMODEL%"
set "ANTHROPIC_DEFAULT_HAIKU_MODEL=%ORMODEL%"
set "CLAUDE_CODE_SUBAGENT_MODEL=%ORMODEL%"
echo.
echo Model: %ORMODEL%  (bedava sinir: dakikada 20, gunde 50 istek)
echo.
call claude
pause
