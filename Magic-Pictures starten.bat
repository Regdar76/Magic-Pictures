@echo off
REM Startet die Magic-Pictures-App per Doppelklick
cd /d "%~dp0"
python "magic_pictures.py"
if errorlevel 1 pause
