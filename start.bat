@echo off
chcp 65001 >nul
title SongShareTool 启动器

:: ── 检测 Python ───────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本。
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: ── 检查 Python 版本 ≥ 3.10 ──────────────────────────────────────────────
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    if %%a LSS 3 (
        echo [错误] Python 版本过低（当前 %PY_VER%），需要 3.10 或以上。
        pause
        exit /b 1
    )
    if %%a EQU 3 if %%b LSS 10 (
        echo [错误] Python 版本过低（当前 %PY_VER%），需要 3.10 或以上。
        pause
        exit /b 1
    )
)

:: ── 创建虚拟环境（如不存在）────────────────────────────────────────────────
if not exist ".venv" (
    echo [信息] 正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 安装。
        pause
        exit /b 1
    )
)

:: ── 激活虚拟环境 ──────────────────────────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── 安装/更新依赖 ──────────────────────────────────────────────────────────
echo [信息] 正在检查依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

:: ── 启动程序 ──────────────────────────────────────────────────────────────
echo [信息] 正在启动程序...
python run.py
if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错，请查看上方错误信息。
    pause
)
