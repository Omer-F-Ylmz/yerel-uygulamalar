@echo off
chcp 65001 >nul
rem Yerel modeller icin bellek dostu Ollama ayarlari (bir kez calistirmak yeter)
echo Yerel modellerin ekran karti ve RAM kullanimini sinirlayan ayarlar yapiliyor...
setx OLLAMA_CONTEXT_LENGTH 131072 >nul
setx OLLAMA_KV_CACHE_TYPE q8_0 >nul
setx OLLAMA_FLASH_ATTENTION 1 >nul
setx OLLAMA_NUM_PARALLEL 1 >nul
setx OLLAMA_MAX_LOADED_MODELS 1 >nul
setx OLLAMA_KEEP_ALIVE 5m >nul
echo   Baglam 128K (Claude Code icin gerekli), onbellek sikistirilmis, ayni anda tek model,
echo   5 dakika kullanilmazsa model bellekten bosaltilir.
echo.
echo Ollama yeniden baslatiliyor (ayarlar ancak boyle gecerli olur)...
taskkill /f /im "ollama app.exe" >nul 2>nul
taskkill /f /im ollama.exe >nul 2>nul
timeout /t 2 /nobreak >nul
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
  start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
  echo Tamam. Simdi ollama_claude.bat ile yerel bir model sec.
) else (
  echo Ollama'yi baslat menusunden kendin ac, sonra ollama_claude.bat'i calistir.
)
echo.
echo Kontrol: model calisirken yeni bir pencerede "ollama ps" yaz;
echo CONTEXT 131072 ve PROCESSOR 100%% GPU gormelisin.
pause
