@echo off
REM Helper script to run the Exam System with the virtual environment properly activated
REM Usage:
REM   run.bat           - Run the application
REM   run.bat test      - Run the test system
REM   run.bat install   - Install dependencies
REM   run.bat help      - Show this help message

setlocal

REM Change to the directory of this script
cd /d "%~dp0"

REM Ensure virtual environment exists
if not exist "venv\" (
  echo Creating virtual environment...
  python -m venv venv
)

REM Show help if requested
if "%1"=="help" (
  echo Exam System Helper Script
  echo ------------------------
  echo Usage:
  echo   run.bat           - Run the application
  echo   run.bat test      - Run the test system
  echo   run.bat install   - Install dependencies
  echo   run.bat help      - Show this help message
  exit /b 0
)

REM Activate virtual environment
call venv\Scripts\activate.bat
echo Virtual environment activated.

REM Initialize database directory if it doesn't exist
if not exist "database\" (
  echo Creating database directory...
  mkdir database
)

REM Install dependencies if requested or if first run
if "%1"=="install" goto install_deps
if not exist "venv\.dependencies_installed" goto install_deps
goto after_install

:install_deps
echo Installing dependencies...
pip install flask werkzeug flask_limiter flask_wtf openpyxl
echo. > venv\.dependencies_installed
echo Dependencies installed successfully.

:after_install

REM Run test system if requested
if "%1"=="test" (
  echo Running test system...
  python test_system.py
  exit /b %errorlevel%
)

REM Default: Run the application
echo Starting Exam System...
echo Access the application at http://localhost:5000
echo Default teacher login: username=teacher, password=admin123
echo Press Ctrl+C to stop the server
python app.py

REM Keep the terminal open if there was an error
if %errorlevel% neq 0 (
  echo Press Enter to exit...
  pause > nul
)

exit /b %errorlevel%