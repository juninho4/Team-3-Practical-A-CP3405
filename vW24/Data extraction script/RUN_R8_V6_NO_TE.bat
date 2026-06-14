@echo off
setlocal
cd /d "%~dp0"
title R8 v6 No TradingEconomics

echo ==========================================
echo R8 v6 No TradingEconomics
echo Outputs:
echo - Finviz closing prices 1W
echo - Finviz 1W performance
echo - Yahoo 11 sector 5D screenshots
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

echo [1/3] Installing dependency...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Chromium...
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install Chromium.
    pause
    exit /b 1
)

echo.
echo [3/3] Taking screenshots...
python r8_v6_no_tradingeconomics.py
if errorlevel 1 (
    echo.
    echo ERROR: Screenshot script failed.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo DONE.
echo Open this folder:
echo %cd%\evidence
echo ==========================================
echo.
pause
endlocal
