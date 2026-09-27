@echo off
rem Double-click this file to open Email Sorter.
rem Keep this black window open while the sorter runs. If something goes
rem wrong, the error appears here: take a screenshot of it.
cd /d "%~dp0"
title Email Sorter

where py >nul 2>nul
if %errorlevel%==0 (
    echo Starting Email Sorter...
    py -3 email_sorter_app.py
    goto :done
)
where python >nul 2>nul
if %errorlevel%==0 (
    echo Starting Email Sorter...
    python email_sorter_app.py
    goto :done
)

echo.
echo  Python is not installed on this computer yet.
echo.
echo  1. Your web browser will now open the Python download page.
echo  2. Download and run the installer.
echo     IMPORTANT: tick the box "Add python.exe to PATH" at the bottom of the first screen.
echo  3. When it finishes, double-click "Start (Windows)" again.
echo.
start https://www.python.org/downloads/
pause
exit /b

:done
if errorlevel 1 (
    echo.
    echo  Something went wrong. Please take a screenshot of this window.
    pause
)
