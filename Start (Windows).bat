@echo off
rem Double-click this file to open Email Sorter.
cd /d "%~dp0"

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 email_sorter_app.py
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw email_sorter_app.py
    exit /b
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
