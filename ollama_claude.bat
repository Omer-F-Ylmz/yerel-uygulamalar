@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Ollama ile calisan Claude Code: ayri, temiz profil (eski eklentiler yuklenmez)
set "CLAUDE_CONFIG_DIR=%USERPROFILE%\.claude-ollama"
if not exist "%CLAUDE_CONFIG_DIR%\skills" mkdir "%CLAUDE_CONFIG_DIR%\skills"
where ollama >nul 2>nul || (echo Ollama bulunamadi. https://ollama.com/download adresinden kur. & pause & exit /b 1)
ollama launch claude --model gemma4:31b-cloud
pause
