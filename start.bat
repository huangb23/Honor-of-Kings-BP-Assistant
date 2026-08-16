@echo off
REM 启动 BP 器（Windows）
REM 用法: 双击 start.bat  或  在项目根目录 start.bat [端口]

REM 切到脚本所在目录（项目根目录），保证相对路径正确
cd /d "%~dp0"

set "PORT=%1"
if "%PORT%"=="" set "PORT=8000"

REM 优先用 win_rate 的 venv 里的 python，找不到则回退系统 python
if exist "win_rate\.venv\Scripts\python.exe" (
    set "PY=win_rate\.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY=python"
    ) else (
        where py >nul 2>nul
        if %errorlevel%==0 (
            set "PY=py"
        ) else (
            echo [ERROR] 找不到 Python，请安装 Python 3 或确认 venv 存在 win_rate\.venv
            pause
            exit /b 1
        )
    )
)

echo 使用解释器: %PY%
echo 启动 BP 服务端口: %PORT%
echo 浏览器打开: http://localhost:%PORT%/index.html
%PY% -u backend\server.py %PORT%
pause