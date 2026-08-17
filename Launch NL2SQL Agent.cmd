@echo off
setlocal
title NL2SQL Agent
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo uv is required but was not found on PATH.
    echo Install uv from https://docs.astral.sh/uv/ and double-click this file again.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo First-time setup: creating the virtual environment and installing dependencies.
    echo This can take a minute.
    echo.
    uv sync --locked
    if errorlevel 1 (
        echo.
        echo Setup failed. See the output above for details.
        pause
        exit /b 1
    )
)

uv run --locked nl2sql-agent serve
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" (
    echo.
    echo NL2SQL Agent stopped with exit code %exit_code%.
    pause
)
exit /b %exit_code%
