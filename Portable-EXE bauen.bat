@echo off
REM ============================================================
REM  Baut eine portable Magic-Pictures.exe (ohne Python noetig)
REM  Ergebnis liegt danach im Ordner "dist".
REM ============================================================
cd /d "%~dp0"

echo PyInstaller wird sichergestellt...
python -m pip install --upgrade pyinstaller >nul 2>&1

echo.
echo Baue portable EXE - bitte warten...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "Magic-Pictures" ^
    --icon "%~dp0icon.ico" ^
    --distpath "dist" ^
    --workpath "build" ^
    --specpath "build" ^
    "magic_pictures.py"

echo.
if exist "dist\Magic-Pictures.exe" (
    echo FERTIG! Die portable App liegt hier:
    echo    %~dp0dist\Magic-Pictures.exe
) else (
    echo Es ist ein Fehler aufgetreten - bitte Meldungen oben pruefen.
)
echo.
pause
