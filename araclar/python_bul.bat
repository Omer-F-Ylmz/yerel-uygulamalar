@echo off
rem Python yorumlayicisini bulup PY degiskenine yazar (PATH ayari gerekmez).
set "PY="
for %%d in ("%LOCALAPPDATA%\Programs\Python\Python313" "%LOCALAPPDATA%\Programs\Python\Python312" "%LOCALAPPDATA%\Programs\Python\Python311" "%ProgramFiles%\Python313" "%ProgramFiles%\Python312" "%ProgramFiles%\Python311") do (
    if not defined PY if exist "%%~d\python.exe" set "PY="%%~d\python.exe""
)
if not defined PY (
    py -3 --version >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python bulunamadi. https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe adresinden kur.
    exit /b 1
)
exit /b 0
