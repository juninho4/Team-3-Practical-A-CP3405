@echo off
setlocal
cd /d "%~dp0"
title R6 One Click Integrated - Connect My Edge

echo ==========================================
echo R6 ONE CLICK INTEGRATED
echo Uses your normal Microsoft Edge login profile
echo Input:  input
echo Q:      output\Q
echo Raw:    output\llm_raw_responses
echo Report: output\llm
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python first and tick "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo [1/4] Installing Python dependency...
python -m pip install -r app\requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [2/4] Installing Edge support...
python -m playwright install msedge

echo.
echo [3/4] Starting your Microsoft Edge with remote debugging...
echo Closing existing Edge processes first...
taskkill /F /IM msedge.exe >nul 2>nul
timeout /t 2 /nobreak >nul

set EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe
if not exist "%EDGE_EXE%" set EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe

if not exist "%EDGE_EXE%" (
    echo ERROR: Microsoft Edge executable not found.
    pause
    exit /b 1
)

start "" "%EDGE_EXE%" --remote-debugging-port=9222 --profile-directory=Default --start-maximized https://chatgpt.com/
timeout /t 5 /nobreak >nul

echo.
echo [4/4] Starting R6 workflow...
python app\r6_integrated_one_click.py --sprint "Current Week" --max-wait 180 --login-wait 120

echo.
pause
endlocal
