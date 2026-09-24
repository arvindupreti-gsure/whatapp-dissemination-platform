@echo off
REM ===================================================================
REM  WhatsApp Dissemination & Analytics Platform : proof of concept
REM  Gsure Technologies Private Limited
REM
REM  Safe to double click. This window stays open on any error so the
REM  message can actually be read.
REM ===================================================================

setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title WhatsApp Dissemination and Analytics Platform

echo.
echo   ================================================================
echo     WhatsApp Dissemination ^& Analytics Platform
echo     Proof of concept  ^|  Gsure Technologies Private Limited
echo   ================================================================
echo.

REM ---------------------------------------------------------- 1. Python
set "PY="
python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if !errorlevel! equ 0 set "PY=python"

if not defined PY (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
  if !errorlevel! equ 0 set "PY=py -3"
)

if not defined PY (
  echo   [X] Python 3.10 or later was not found.
  echo.
  echo       Checked both "python" and "py -3" on PATH.
  echo.
  echo       Install Python 3.11 or later from https://www.python.org/downloads/
  echo       During setup, tick "Add python.exe to PATH".
  echo.
  echo       If Python IS installed, open a NEW Command Prompt and run:
  echo           python --version
  echo       If that opens the Microsoft Store instead, disable the alias at
  echo       Settings ^> Apps ^> Advanced app settings ^> App execution aliases
  echo       and switch off both "python.exe" and "python3.exe" entries.
  echo.
  goto :fail
)

for /f "tokens=*" %%V in ('!PY! -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%V"
echo   [1/4] Python !PYVER! found
echo.

REM ---------------------------------------------------- 2. Dependencies
set "IMPORTS=import fastapi, uvicorn, sqlalchemy, httpx, openpyxl, reportlab, cryptography, multipart"
!PY! -c "!IMPORTS!" >nul 2>&1
if !errorlevel! equ 0 (
  echo   [2/4] Dependencies already present
) else (
  echo   [2/4] Installing dependencies, this may take a minute...
  echo.
  !PY! -m pip install --disable-pip-version-check -r requirements.txt
  echo.
  !PY! -c "!IMPORTS!" >nul 2>&1
  if !errorlevel! neq 0 (
    echo   [X] Dependencies are still missing after the install attempt.
    echo.
    echo       Run this by hand to see the real error:
    echo           !PY! -m pip install -r requirements.txt
    echo.
    echo       If pip cannot reach the network, you are behind a proxy or
    echo       offline. Set HTTPS_PROXY, or install the packages listed in
    echo       requirements.txt from an internal mirror.
    echo.
    goto :fail
  )
  echo   [2/4] Dependencies installed
)
echo.

REM ------------------------------------------------------------ 3. Port
set "WANT=%WDAP_PORT%"
if "!WANT!"=="" set "WANT=8000"
set "PORT="
REM The probe binds rather than connects: a bound-but-not-accepting socket
REM still answers "refused", so a connect test reports a busy port as free
REM and uvicorn then dies with WSAEADDRINUSE. See tools\freeport.py.
for /f "usebackq tokens=*" %%P in (`!PY! "tools\freeport.py" !WANT! 8025 2^>nul`) do set "PORT=%%P"

if not defined PORT (
  echo   [X] No free port between !WANT! and 8025.
  echo       Close whatever is using them, or set a port explicitly:
  echo           set WDAP_PORT=9100 ^&^& run.bat
  echo.
  goto :fail
)

if not "!PORT!"=="!WANT!" (
  echo   [3/4] Port !WANT! is busy, using !PORT! instead
) else (
  echo   [3/4] Port !PORT! is free
)
echo.

REM -------------------------------------------------------- 4. Settings
if "%WDAP_CHANNEL%"==""    set "WDAP_CHANNEL=simulator"
if "%WDAP_TIME_SCALE%"=="" set "WDAP_TIME_SCALE=0.01"
set "WDAP_PORT=!PORT!"
set "WDAP_PUBLIC_URL=http://127.0.0.1:!PORT!"

echo   [4/4] Starting the platform
echo.
echo   ----------------------------------------------------------------
echo     URL          http://127.0.0.1:!PORT!
echo     Sign in      admin@gsuretech.com  /  Gsure@2026
echo     Channel      !WDAP_CHANNEL!   (simulator sends nothing)
echo     Time scale   !WDAP_TIME_SCALE!   (15m snapshot lands in ~9s)
echo   ----------------------------------------------------------------
echo.
echo   First run seeds 5,000 groups. Allow a few seconds.
echo   Press Ctrl+C to stop the server.
echo.

if not "%WDAP_NO_BROWSER%"=="1" (
  start "" !PY! -c "import time,webbrowser; time.sleep(6); webbrowser.open('http://127.0.0.1:!PORT!')" >nul 2>&1
)

cd backend
!PY! -m uvicorn app:app --host 127.0.0.1 --port !PORT!
set "RC=!errorlevel!"
cd ..

echo.
if !RC! neq 0 (
  echo   [X] The server exited with code !RC!.
  echo       The error text is just above this line.
) else (
  echo   Server stopped.
)
goto :fail

:fail
echo.
echo   Press any key to close this window...
pause >nul
endlocal
exit /b
