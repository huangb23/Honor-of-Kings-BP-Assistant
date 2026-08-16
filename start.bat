@echo off
cd /d "%~dp0"

set "PORT=%1"
if "%PORT%"=="" set "PORT=8000"

where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY=py"
    ) else (
        echo [ERROR] Python not found
        pause
        exit /b 1
    )
)

echo Using Python: %PY%
echo Starting server on port: %PORT%
echo Open browser: http://localhost:%PORT%/index.html
%PY% -u backend\server.py %PORT%
pause