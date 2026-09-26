@echo off
setlocal DisableDelayedExpansion
set "PYTHON_COMMAND="
set "PYTHON_VERSION=3.13.5"
set "PYTHON_ARCH=amd64"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PYTHON_ARCH=arm64"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-%PYTHON_ARCH%.exe"
set "FFMPEG_URL=https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/download/b6.1.2-rc.1/ffmpeg-win32-x64"
set "FFPROBE_URL=https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/download/b6.1.2-rc.1/ffprobe-win32-x64"
set "RELEASE_PAGE=https://github.com/descriptinc/ffmpeg-ffprobe-static/releases/tag/b6.1.2-rc.1"
set "TOOLS_DIR=%~dp0"
set "WORK_DIR=%TEMP%\mediatocapcut-setup"
set "PYTHON_CHECK=import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)"

if exist "%TOOLS_DIR%ffmpeg.exe" set "PATH=%TOOLS_DIR%;%PATH%"
if exist "%TOOLS_DIR%ffprobe.exe" set "PATH=%TOOLS_DIR%;%PATH%"

call :detect_python
if not defined PYTHON_COMMAND call :offer_python
if not defined PYTHON_COMMAND goto missing_python

call :detect_media_tools
if not defined MEDIA_TOOLS_READY call :offer_media_tools
if not defined MEDIA_TOOLS_READY goto missing_tools

%PYTHON_COMMAND% "%~dp0MediaToCapcut.py" %*
set "STATUS=%ERRORLEVEL%"
if not "%STATUS%"=="0" (
    echo.
    echo ERROR: MediaToCapcut exited with code %STATUS%.
    pause
)
exit /b %STATUS%


:detect_python
set "PYTHON_COMMAND="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "%PYTHON_CHECK%" >nul 2>nul
    if not errorlevel 1 set "PYTHON_COMMAND=py -3"
)
if defined PYTHON_COMMAND exit /b 0
where python >nul 2>nul
if not errorlevel 1 (
    python -c "%PYTHON_CHECK%" >nul 2>nul
    if not errorlevel 1 set "PYTHON_COMMAND=python"
)
exit /b 0


:offer_python
if defined MEDIATOCAPCUT_NO_SETUP exit /b 0
echo.
echo Python 3 was not found on this computer.
choice /C YN /N /M "Download and install Python %PYTHON_VERSION% now? [Y/N]: "
if errorlevel 2 exit /b 0
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%" >nul 2>nul
echo Downloading the Python %PYTHON_VERSION% installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%WORK_DIR%\python-installer.exe' -UseBasicParsing } catch { Write-Host $_; exit 1 }"
if errorlevel 1 (
    echo ERROR: The Python installer could not be downloaded.
    exit /b 0
)
echo Installing Python for the current user. This can take a minute...
start "" /wait "%WORK_DIR%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 AssociateFiles=0 Shortcuts=0
set "PF86=%ProgramFiles(x86)%"
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%~fD\python.exe" set "PYTHON_COMMAND=%%~fD\python.exe"
if not defined PYTHON_COMMAND for /d %%D in ("%ProgramFiles%\Python3*") do if exist "%%~fD\python.exe" set "PYTHON_COMMAND=%%~fD\python.exe"
if not defined PYTHON_COMMAND for /d %%D in ("%PF86%\Python3*") do if exist "%%~fD\python.exe" set "PYTHON_COMMAND=%%~fD\python.exe"
if not defined PYTHON_COMMAND exit /b 0
"%PYTHON_COMMAND%" -c "%PYTHON_CHECK%" >nul 2>nul
if not errorlevel 1 exit /b 0
set "PYTHON_COMMAND="
exit /b 0


:detect_media_tools
set "MEDIA_TOOLS_READY="
where ffmpeg.exe >nul 2>nul
if errorlevel 1 exit /b 0
where ffprobe.exe >nul 2>nul
if errorlevel 1 exit /b 0
set "MEDIA_TOOLS_READY=1"
exit /b 0


:offer_media_tools
if defined MEDIATOCAPCUT_NO_SETUP exit /b 0
echo.
echo ffmpeg.exe and ffprobe.exe were not found on this computer.
echo Each file is about 120 MB and will be saved next to this script:
echo %TOOLS_DIR%
choice /C YN /N /M "Download ffmpeg and ffprobe now? [Y/N]: "
if errorlevel 2 exit /b 0
if not exist "%WORK_DIR%" mkdir "%WORK_DIR%" >nul 2>nul
echo Downloading ffmpeg.exe. This can take a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%FFMPEG_URL%' -OutFile '%WORK_DIR%\ffmpeg.exe' -UseBasicParsing } catch { Write-Host $_; exit 1 }"
if errorlevel 1 (
    echo ERROR: ffmpeg.exe could not be downloaded.
    exit /b 0
)
echo Downloading ffprobe.exe...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%FFPROBE_URL%' -OutFile '%WORK_DIR%\ffprobe.exe' -UseBasicParsing } catch { Write-Host $_; exit 1 }"
if errorlevel 1 (
    echo ERROR: ffprobe.exe could not be downloaded.
    exit /b 0
)
copy /y "%WORK_DIR%\ffmpeg.exe" "%TOOLS_DIR%ffmpeg.exe" >nul
if errorlevel 1 (
    echo ERROR: ffmpeg.exe could not be saved to %TOOLS_DIR%
    exit /b 0
)
copy /y "%WORK_DIR%\ffprobe.exe" "%TOOLS_DIR%ffprobe.exe" >nul
if errorlevel 1 (
    echo ERROR: ffprobe.exe could not be saved to %TOOLS_DIR%
    exit /b 0
)
set "PATH=%TOOLS_DIR%;%PATH%"
call :detect_media_tools
exit /b 0


:missing_python
echo.
echo ERROR: Python 3 is required to run this tool.
echo Download and install Python 3 from:
echo https://www.python.org/downloads/
echo Then run this file again.
pause
exit /b 1


:missing_tools
echo.
echo ERROR: ffmpeg.exe and ffprobe.exe are required to run this tool.
echo.
echo Download both files from:
echo %RELEASE_PAGE%
echo.
echo   ffmpeg-win32-x64   save as ffmpeg.exe
echo   ffprobe-win32-x64  save as ffprobe.exe
echo.
echo Save both files in this folder:
echo %TOOLS_DIR%
echo Or add their folder to PATH, then run this file again.
pause
exit /b 1
