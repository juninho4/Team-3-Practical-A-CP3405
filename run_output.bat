@echo off
setlocal

cd /d "%~dp0"

set "WEEK=vW29"

git rev-parse --is-inside-work-tree >nul 2>&1

if errorlevel 1 (
    echo ERROR: This is not a Git repository.
    echo Put this BAT file beside README.md.
    pause
    exit /b 1
)

if not exist "%WEEK%" (
    echo ERROR: %WEEK% folder was not found.
    echo Please create %WEEK% beside vW28 first.
    pause
    exit /b 1
)

echo Pulling latest changes from GitHub...
git pull --rebase --autostash origin main

if errorlevel 1 (
    echo.
    echo ERROR: Git pull failed.
    pause
    exit /b 1
)

echo.
echo Adding files from %WEEK%...
git add "%WEEK%"

if errorlevel 1 (
    echo.
    echo ERROR: Git could not add %WEEK%.
    pause
    exit /b 1
)

echo.
echo Checking for changes...
git diff --cached --quiet

if not errorlevel 1 (
    echo No new or changed files were found in %WEEK%.
    echo Nothing needs to be uploaded.
    pause
    exit /b 0
)

echo.
echo Creating commit...
git commit -m "Update %WEEK% files"

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
echo Uploaded folder: %WEEK%
pause
