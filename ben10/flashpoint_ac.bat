@echo off
rem Flashpoint'in kendi penceresini dogru klasorden acar (oyunu elle secmek icin)
set /p KOK=<"%~dp0fp_yolu.txt"
start "" /D "%KOK%Launcher" "%KOK%Launcher\Flashpoint.exe"
