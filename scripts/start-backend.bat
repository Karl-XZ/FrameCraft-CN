@echo off
cd /d "%~dp0.."
call "%~dp0setup-deps.bat"
if errorlevel 1 exit /b 1
if "%FRAMECRAFT_BACKEND_HOST%"=="" set FRAMECRAFT_BACKEND_HOST=0.0.0.0
if "%FRAMECRAFT_BACKEND_PORT%"=="" set FRAMECRAFT_BACKEND_PORT=8022
echo [FrameCraft] Starting single-agent backend on http://%FRAMECRAFT_BACKEND_HOST%:%FRAMECRAFT_BACKEND_PORT%
set PYTHONPATH=backend
if "%FRAMECRAFT_BACKEND_RELOAD%"=="1" (
  backend\venv\Scripts\python.exe -m uvicorn app.main:app --host %FRAMECRAFT_BACKEND_HOST% --port %FRAMECRAFT_BACKEND_PORT% --reload --reload-exclude uploads/* --reload-exclude outputs/*
) else (
  backend\venv\Scripts\python.exe -m uvicorn app.main:app --host %FRAMECRAFT_BACKEND_HOST% --port %FRAMECRAFT_BACKEND_PORT%
)
