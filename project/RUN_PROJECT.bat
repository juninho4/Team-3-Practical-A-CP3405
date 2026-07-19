@echo off
setlocal
cd /d "%~dp0"
title Market Intelligence Integrated Pipeline

echo ============================================================================
echo MARKET INTELLIGENCE INTEGRATED PIPELINE
echo R6 -^> R3 -^> R4 -^> R5 -^> Organize -^> R8
echo ============================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python and select "Add Python to PATH".
    pause
    exit /b 1
)

echo [Setup] Installing/updating Python packages...
python -m pip install -r app\requirements.txt
if errorlevel 1 (
    echo ERROR: Python package installation failed.
    pause
    exit /b 1
)

echo.
echo Starting pipeline...
python app\run_integrated_pipeline.py
set PIPELINE_EXIT=%ERRORLEVEL%

echo.
if not "%PIPELINE_EXIT%"=="0" (
    echo PIPELINE FAILED. Exit code: %PIPELINE_EXIT%
) else (
    echo PIPELINE COMPLETED SUCCESSFULLY.
)
echo.
pause
exit /b %PIPELINE_EXIT%
