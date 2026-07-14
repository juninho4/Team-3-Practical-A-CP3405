@echo off

cd /d "%~dp0"

git pull --rebase origin main

REM fill in the automated execution command here.

git add data\market_closes\output

git diff --cached --quiet

if errorlevel 1 (
    git commit -m "Auto update output"
    git push origin main
)

pause
