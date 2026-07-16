@echo off
setlocal

cd /d "%~dp0"


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

if exist "data\market_closes" (
    git add "data\market_closes"
)

if exist "vW28\evidence" (
    git add "vW28\evidence"
)

if exist "vW28\Technical Agent" (
    git add "vW28\Technical Agent"
)

if exist "vW25\llm\R6_one_click_integrated_answer_only_fixed\output" (
    git add "vW25\llm\R6_one_click_integrated_answer_only_fixed\output"
)

git add fed_market_report_*.md 2>nul
git add technical_agent_output_*.csv 2>nul
git add technical_agent_output_*.json 2>nul
git add charts 2>nul

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

git commit -m "Update automated agent outputs"

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
echo =========================================
echo Upload completed successfully!
echo =========================================
echo.

pause
