@echo off
setlocal
cd /d "%~dp0"

:: 1. Check Python Launcher (py.exe -3)
py.exe -3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py.exe -3"
    goto :RUN
)

:: 2. Check explicit Python versions in LocalAppData and Program Files
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :RUN
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :RUN
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :RUN
)
if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe -3"
    goto :RUN
)
if exist "C:\Program Files\Python312\python.exe" (
    set "PY_CMD=C:\Program Files\Python312\python.exe"
    goto :RUN
)

:: 3. Test standard python command
python.exe -c "import sys; sys.exit(0)" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python.exe"
    goto :RUN
)

echo [Statr Error] Python 3.10+ could not be found automatically.
echo Please install Python 3.12 from https://www.python.org/downloads/
pause
exit /b 1

:RUN
if "%1"=="" (
    %PY_CMD% main.py run
) else (
    %PY_CMD% main.py %*
)
