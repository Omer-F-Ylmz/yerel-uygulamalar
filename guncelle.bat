@echo off
cd /d "%~dp0"
rem .gitignore'u proje yonetiyor; yerel degisiklik guncellemeyi engellemesin
git checkout -- .gitignore 2>nul
git pull --no-rebase --no-edit && goto son
echo.
echo Yerel degisiklikler guncellemeyi engelledi; kenara alinip tekrar deneniyor...
git stash
git pull --no-rebase --no-edit
git stash pop || echo Kenara alinan degisiklikler geri yuklenemedi; "git stash list" ile duruyorlar.
:son
pause
