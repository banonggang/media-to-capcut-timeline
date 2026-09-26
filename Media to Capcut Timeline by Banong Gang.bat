@echo off
setlocal DisableDelayedExpansion
set "PYTHON_COMMAND="

if exist "%~dp0ffmpeg.exe" set "PATH=%~dp0;%PATH%"
if exist "%~dp0ffprobe.exe" set "PATH=%~dp0;%PATH%"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
    if not errorlevel 1 set "PYTHON_COMMAND=py -3"
)

if not defined PYTHON_COMMAND (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
        if not errorlevel 1 set "PYTHON_COMMAND=python"
    )
)

if not defined PYTHON_COMMAND (
    echo ERROR: Python 3 is required.
    pause
    exit /b 1
)

where ffmpeg.exe >nul 2>nul
if errorlevel 1 goto missing_tools
where ffprobe.exe >nul 2>nul
if errorlevel 1 goto missing_tools

%PYTHON_COMMAND% "%~dp0MediaToCapcut.py" %*
set "STATUS=%ERRORLEVEL%"
if not "%STATUS%"=="0" (
    echo.
    echo ERROR: AutoFlow exited with code %STATUS%.
    pause
)
exit /b %STATUS%

:missing_tools
echo ERROR: ffmpeg.exe and ffprobe.exe are required.
echo.
echo Download both files from:
echo https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/tag/b6.1.2-rc.1
echo.
echo Extract ffmpeg.exe and ffprobe.exe into this folder, or add their folder to PATH.
echo Then run this file again.
pause
exit /b 1
