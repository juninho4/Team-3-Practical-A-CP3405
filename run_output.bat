@echo off
setlocal

cd /d "%~dp0"

REM Change only this line for the next week, for example vW30
set "WEEK=vW29"

git rev-parse --is-inside-work-tree >nul 2>&1

if errorlevel 1 (
    echo ERROR: This folder is not a Git repository.
    echo Put this file beside README.md in the cloned project folder.
    pause
    exit /b 1
)

echo Pulling latest changes from GitHub...
git pull --rebase origin main

if errorlevel 1 (
    echo.
    echo ERROR: Git pull failed.
    echo Please resolve the conflict first.
    pause
    exit /b 1
)

echo.
echo Adding generated output files...

REM Shared market outputs
if exist "data\market_closes" (
    git add "data\market_closes"
)

REM Current-week outputs
if exist "%WEEK%\output" (
    git add "%WEEK%\output"
)

if exist "%WEEK%\evidence" (
    git add "%WEEK%\evidence"
)

if exist "%WEEK%\Technical Agent" (
    git add "%WEEK%\Technical Agent"
)

if exist "%WEEK%\agents" (
    git add "%WEEK%\agents"
)

REM Existing R6 output location
if exist "vW25\llm\R6_one_click_integrated_answer_only_fixed\output" (
    git add "vW25\llm\R6_one_click_integrated_answer_only_fixed\output"
)

REM Root-level generated files
git add fed_market_report_*.md 2>nul
git add technical_agent_output_*.csv 2>nul
git add technical_agent_output_*.json 2>nul

if exist "charts" (
    git add "charts"
)

echo.
echo Checking for new changes...

git diff --cached --quiet

if not errorlevel 1 (
    echo No new output files were found.
    echo Nothing needs to be uploaded.
    pause
    exit /b 0
)

echo.
echo Creating commit...

git commit -m "Update %WEEK% automated agent outputs"

if errorlevel 1 (
    echo.
    echo ERROR: Git commit failed.
    pause
    exit /b 1
)

echo.
echo Uploading to GitHub...

git push origin main

if errorlevel 1 (
    echo.
    echo ERROR: Upload failed.
    echo Check your GitHub login and internet connection.
    pause
    exit /b 1
)

echo.
echo Upload completed successfully.
echo Week: %WEEK%
echo.

pause
