@echo off
rem Ben 10: Battle Ready - ilk seferde kurar, sonra oyunu acar
cd /d "%~dp0ben10"
if not exist "fp_yolu.txt" call kur.bat
if exist "fp_yolu.txt" call oyna.bat
