@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

title Build - Kejyn Stinger Exporter

echo.
echo ==================================================
echo   KEJYN STINGER EXPORTER - BUILD WINDOWS
echo ==================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        echo [ERREUR] Python 3.11+ est requis.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/6] Creation de l'environnement Python...
    %PY% -m venv .venv
    if errorlevel 1 goto :error
)

set "VPY=.venv\Scripts\python.exe"

echo [2/6] Installation des dependances...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo [3/6] Telechargement de Chromium Playwright...
if exist "build\browsers" rmdir /s /q "build\browsers"
mkdir "build\browsers"
set "PLAYWRIGHT_BROWSERS_PATH=%CD%\build\browsers"
"%VPY%" -m playwright install chromium
if errorlevel 1 goto :error

echo [4/6] Construction de l'application...
if exist "dist" rmdir /s /q "dist"
if exist "build\pyinstaller" rmdir /s /q "build\pyinstaller"

"%VPY%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "KejynStingerExporter" ^
    --distpath "dist" ^
    --workpath "build\pyinstaller" ^
    --specpath "build" ^
    --collect-all playwright ^
    --collect-all imageio_ffmpeg ^
    "app\KejynStingerExporter.py"

if errorlevel 1 goto :error

echo [5/6] Recherche de Inno Setup...
set "ISCC="

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
)

if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
)

if not defined ISCC (
    echo.
    echo [ERREUR] Inno Setup 6 n'est pas installe.
    echo Telecharge-le une fois depuis https://jrsoftware.org/isinfo.php
    echo puis relance scripts\build_windows_installer.bat
    echo.
    pause
    exit /b 1
)

echo [6/6] Construction de Setup.exe...
if not exist "release" mkdir "release"
"%ISCC%" "installer\KejynStingerExporter.iss"
if errorlevel 1 goto :error

echo.
echo ==================================================
echo   BUILD TERMINE
echo ==================================================
echo.
echo Installateur :
echo   release\KejynStingerExporter-Setup-1.0.0.exe
echo.
pause
exit /b 0

:error
echo.
echo [ERREUR] Le build a echoue.
pause
exit /b 1
