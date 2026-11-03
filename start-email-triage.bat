@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Hermes Email Triage

set "SCRIPT_DIR=%~dp0"

set "TRIAGE_CHAT=Outlook Triage"
set "TRIAGE_PROMPT=Triage my Outlook inbox for the last 7 days. Classify, prioritize, summarize, and propose organization. Do not change anything yet."

if not defined HERMES_HOME set "HERMES_HOME=%LOCALAPPDATA%\hermes"
if not defined EMAIL_TRIAGE_HOME set "EMAIL_TRIAGE_HOME=%USERPROFILE%\email-triage"

set "PATH=%HERMES_HOME%\bin;%PATH%"
set "LOG=%TEMP%\email-triage-start.log"
set "HERMES="
set "APP_DIR="
set "FAIL_MSG="

call :log "=== Hermes email triage launcher ==="

rem --- Resolve Hermes ---
if exist "%HERMES_HOME%\bin\hermes.exe" set "HERMES=%HERMES_HOME%\bin\hermes.exe"
if not defined HERMES (
    where hermes >nul 2>nul
    if not errorlevel 1 set "HERMES=hermes"
)
if not defined HERMES (
    set "FAIL_MSG=Hermes was not found. Run install-email-triage.bat first."
    goto :fail
)

rem --- Resolve project ---
if exist "%SCRIPT_DIR%clawlink-outlook\scripts\install.ps1" (
    set "APP_DIR=%SCRIPT_DIR%clawlink-outlook"
) else if exist "%SCRIPT_DIR%scripts\install.ps1" (
    set "APP_DIR=%SCRIPT_DIR%"
) else if exist "%EMAIL_TRIAGE_HOME%\clawlink-outlook\scripts\install.ps1" (
    set "APP_DIR=%EMAIL_TRIAGE_HOME%\clawlink-outlook"
) else (
    set "FAIL_MSG=Email triage project was not found. Run install-email-triage.bat first."
    goto :fail
)

call :log "Project: !APP_DIR!"

echo.
echo ClawLink pairing is separate from Outlook. Connect Outlook at:
echo   https://claw-link.dev/integrations/outlook
echo.
echo First prompt:
echo   %TRIAGE_PROMPT%
echo.

rem --- Open Hermes Desktop ---
call :log "Opening Hermes Desktop in !APP_DIR!..."
call "%HERMES%" desktop --cwd "!APP_DIR!"
if errorlevel 1 (
    set "FAIL_MSG=Could not open Hermes Desktop."
    goto :fail
)

rem --- Ensure the triage chat exists ---
for %%I in ("!APP_DIR!") do set "WORK_DIR=%%~fI"
if "!WORK_DIR:~-1!"=="\" set "WORK_DIR=!WORK_DIR:~0,-1!"
call :log "Checking for existing chat '%TRIAGE_CHAT%'..."
set "CHAT_FOUND="
for /f "delims=" %%L in ('call "%HERMES%" sessions list --limit 1000 2^>nul ^| findstr /i /c:"%TRIAGE_CHAT%"') do set "CHAT_FOUND=1"

if defined CHAT_FOUND (
    call :log "Chat '%TRIAGE_CHAT%' already exists; leaving it unchanged."
    exit /b 0
)

call :log "Chat '%TRIAGE_CHAT%' not found. Creating it and sending the triage prompt..."
call "%HERMES%" chat --in "!WORK_DIR!" -c "%TRIAGE_CHAT%" --create-if-missing --source cli -q "%TRIAGE_PROMPT%" --oneshot
if errorlevel 1 (
    set "FAIL_MSG=Could not create chat '%TRIAGE_CHAT%' or send the triage prompt."
    goto :fail
)
call :log "Chat '%TRIAGE_CHAT%' created and prompted."
exit /b 0

:log
echo [%date% %time%] %~1
>>"%LOG%" 2>nul echo [%date% %time%] %~1
goto :eof

:fail
echo.
echo [ERROR] %FAIL_MSG%
>>"%LOG%" 2>nul echo [ERROR] %FAIL_MSG%
echo Log: %LOG%
pause
exit /b 1
