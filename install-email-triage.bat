@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Hermes Email Triage Setup

set "SCRIPT_DIR=%~dp0"
set "DEFAULT_REPO_URL=https://github.com/Ramshad-dev/email-triage.git"
set "DRY_RUN=0"

if /i "%~1"=="--dry-run" (
    set "DRY_RUN=1"
    shift
)
set "REPO_URL=%~1"
if not defined REPO_URL set "REPO_URL=%DEFAULT_REPO_URL%"

if not defined HERMES_HOME set "HERMES_HOME=%LOCALAPPDATA%\hermes"
if not defined EMAIL_TRIAGE_HOME set "EMAIL_TRIAGE_HOME=%USERPROFILE%\email-triage"

set "PATH=%HERMES_HOME%\bin;%PATH%"
set "LOG=%TEMP%\email-triage-install.log"
set "HERMES="
set "GIT="
set "GIT_MISSING="
set "APP_DIR="
set "FAIL_MSG="

call :log "=== Hermes email triage setup ==="
call :log "Repo: %REPO_URL%"
call :log "Hermes home: %HERMES_HOME%"
call :log "Project home: %EMAIL_TRIAGE_HOME%"
if "%DRY_RUN%"=="1" call :log "Mode: dry run"

rem --- Step 1: Hermes ---
call :log "[1/7] Checking Hermes..."
if exist "%HERMES_HOME%\bin\hermes.exe" set "HERMES=%HERMES_HOME%\bin\hermes.exe"
if not defined HERMES (
    where hermes >nul 2>nul
    if not errorlevel 1 set "HERMES=hermes"
)

if not defined HERMES (
    if "%DRY_RUN%"=="1" (
        call :log "[dry-run] Would install Hermes from the official installer."
        set "HERMES=%HERMES_HOME%\bin\hermes.exe"
    ) else (
        call :log "Hermes not found. Installing..."
        powershell -NoProfile -ExecutionPolicy Bypass -Command "iex (irm https://hermes-agent.nousresearch.com/install.ps1)"
        if errorlevel 1 (
            set "FAIL_MSG=Hermes installation failed."
            goto :fail
        )
        if exist "%HERMES_HOME%\bin\hermes.exe" set "HERMES=%HERMES_HOME%\bin\hermes.exe"
        if not defined HERMES (
            where hermes >nul 2>nul
            if not errorlevel 1 set "HERMES=hermes"
        )
        if not defined HERMES (
            set "FAIL_MSG=Hermes installed but the launcher was not found. Open a new terminal and rerun this batch."
            goto :fail
        )
    )
)

if "%DRY_RUN%"=="0" (
    call "%HERMES%" --version
    if errorlevel 1 (
        set "FAIL_MSG=Hermes is not runnable."
        goto :fail
    )
)

rem --- Step 2: Project ---
call :log "[2/7] Resolving project files..."
if exist "%SCRIPT_DIR%clawlink-outlook\scripts\install.ps1" (
    set "APP_DIR=%SCRIPT_DIR%clawlink-outlook"
    call :log "Using local project: !APP_DIR!"
) else if exist "%SCRIPT_DIR%scripts\install.ps1" (
    set "APP_DIR=%SCRIPT_DIR%"
    call :log "Using local project: !APP_DIR!"
) else (
    set "TARGET_ROOT=%EMAIL_TRIAGE_HOME%"
    if "%DRY_RUN%"=="1" (
        call :log "[dry-run] Would clone %REPO_URL% into !TARGET_ROOT!"
        set "APP_DIR=!TARGET_ROOT!\clawlink-outlook"
    ) else (
        if exist "!TARGET_ROOT!\.git" (
            call :log "Updating existing clone: !TARGET_ROOT!"
            call :find_git
            if defined GIT_MISSING (
                set "FAIL_MSG=Git was not found. Install Git or let Hermes install its bundled Git, then rerun."
                goto :fail
            )
            "!GIT!" -C "!TARGET_ROOT!" pull --ff-only
            if errorlevel 1 (
                set "FAIL_MSG=Git pull failed. Resolve the repository state and rerun."
                goto :fail
            )
        ) else (
            if exist "!TARGET_ROOT!" (
                dir /b /a "!TARGET_ROOT!" | findstr . >nul
                if not errorlevel 1 (
                    set "FAIL_MSG=Target exists but is not a Git repository: !TARGET_ROOT!. Move it or set EMAIL_TRIAGE_HOME."
                    goto :fail
                )
            )
            call :log "Cloning %REPO_URL% into !TARGET_ROOT!..."
            call :find_git
            if defined GIT_MISSING (
                set "FAIL_MSG=Git was not found. Install Git or let Hermes install its bundled Git, then rerun."
                goto :fail
            )
            "!GIT!" clone --depth 1 "%REPO_URL%" "!TARGET_ROOT!"
            if errorlevel 1 (
                set "FAIL_MSG=Git clone failed."
                goto :fail
            )
        )
        set "APP_DIR=!TARGET_ROOT!\clawlink-outlook"
    )
)

if "%DRY_RUN%"=="0" (
    if not exist "%APP_DIR%\scripts\install.ps1" (
        set "FAIL_MSG=Project layout is missing scripts\install.ps1 under %APP_DIR%."
        goto :fail
    )
)

rem --- Step 3: Model ---
call :log "[3/7] Configuring Hermes model/provider..."
if "%DRY_RUN%"=="1" (
    call :log "[dry-run] Would run: hermes setup --quick"
) else (
    call "%HERMES%" setup --quick
    if errorlevel 1 (
        set "FAIL_MSG=Hermes setup failed or was canceled. Run 'hermes setup' manually, then rerun this batch."
        goto :fail
    )
)

rem --- Step 4: ClawLink plugin ---
call :log "[4/7] Checking the ClawLink plugin..."
if "%DRY_RUN%"=="1" (
    call :log "[dry-run] Would ensure ClawLink-HQ/hermes-plugin is installed and enabled."
) else (
    call "%HERMES%" plugins list --plain --enabled | findstr /i /c:"clawlink" >nul
    if errorlevel 1 (
        call :log "Installing the ClawLink plugin..."
        call "%HERMES%" plugins install ClawLink-HQ/hermes-plugin --enable
        if errorlevel 1 (
            set "FAIL_MSG=ClawLink plugin installation failed."
            goto :fail
        )
    ) else (
        call :log "ClawLink plugin is already enabled."
    )
)

rem --- Step 5: Pairing ---
call :log "[5/7] Checking ClawLink pairing..."
if "%DRY_RUN%"=="1" (
    call :log "[dry-run] Would pair ClawLink if 'hermes mcp test clawlink' fails."
) else (
    call "%HERMES%" mcp test clawlink >nul 2>nul
    if errorlevel 1 (
        call :log "Pairing ClawLink. Approve the printed link in your browser."
        call "%HERMES%" clawlink setup
        if errorlevel 1 (
            set "FAIL_MSG=ClawLink pairing failed."
            goto :fail
        )
        call "%HERMES%" mcp test clawlink
        if errorlevel 1 (
            set "FAIL_MSG=ClawLink MCP test failed after pairing."
            goto :fail
        )
    ) else (
        call :log "ClawLink is already paired."
    )
)

rem --- Step 6: Skill ---
call :log "[6/7] Installing the Outlook triage skill..."
if "%DRY_RUN%"=="1" (
    call :log "[dry-run] Would run the skill install script under %APP_DIR%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%\scripts\install.ps1"
    if errorlevel 1 (
        set "FAIL_MSG=Skill installation failed."
        goto :fail
    )
    call "%HERMES%" skills list --source local | findstr /i /c:"outlook-clawlink-triage" >nul
    if errorlevel 1 (
        set "FAIL_MSG=Skill was not found after installation."
        goto :fail
    )
)

rem --- Step 7: Launch ---
call :log "[7/7] Preparing to launch Hermes..."
if "%DRY_RUN%"=="1" (
    call :log "[dry-run] Would launch Hermes in %APP_DIR% with -s outlook-clawlink-triage"
    call :log "Dry run complete. No changes made."
    exit /b 0
)

echo.
echo ClawLink pairing is separate from Outlook. Connect Outlook at:
echo   https://claw-link.dev/integrations/outlook
echo.
echo Suggested first prompt:
echo   Triage my Outlook inbox for the last 7 days. Classify, prioritize,
echo   summarize, and propose organization. Do not change anything yet.
echo.
call :log "Launching Hermes with outlook-clawlink-triage..."
timeout /t 5 /nobreak >nul 2>nul
pushd "%APP_DIR%"
if errorlevel 1 (
    set "FAIL_MSG=Could not open the project directory: %APP_DIR%."
    goto :fail
)
call "%HERMES%" -s outlook-clawlink-triage
set "RC=!ERRORLEVEL!"
popd
exit /b !RC!

:find_git
if defined GIT exit /b 0
set "GIT_MISSING="
where git >nul 2>nul
if not errorlevel 1 (
    set "GIT=git"
    exit /b 0
)
for /d %%D in ("%HERMES_HOME%\tools\git-*") do (
    if not defined GIT if exist "%%~fD\bin\git.exe" set "GIT=%%~fD\bin\git.exe"
)
if not defined GIT set "GIT_MISSING=1"
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
