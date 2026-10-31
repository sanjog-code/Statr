@echo off
setlocal
cd /d "%~dp0"

:: Ensure Python is found
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    )
)

if "%1"=="" (
    python main.py run
) else (
    python main.py %*
)
pause
