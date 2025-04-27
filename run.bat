@echo off
REM Helper script to run the Exam System with the virtual environment properly activated
REM Usage:
REM   run.bat           - Run the application
REM   run.bat test      - Run the test system
REM   run.bat install   - Install dependencies
REM   run.bat help      - Show this help message

setlocal EnableExtensions

REM Change to the directory of this script
cd /d "%~dp0"

REM Check if Python is installed and available in PATH
where python >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: Python is not found in your PATH.
  echo Please install Python and make sure it's added to your PATH.
  echo Press any key to exit...
  pause >nul
  exit /b 1
)

REM Show Python version
python --version

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

REM Detect if running under MSYS2/MinGW
python -c "import sys; print('MINGW' if 'mingw' in sys.executable.lower() else 'STANDARD')" > "%TEMP%\python_type.txt"
set /p PYTHON_TYPE=<"%TEMP%\python_type.txt"
del "%TEMP%\python_type.txt"

echo Python environment type: %PYTHON_TYPE%

REM If using MSYS2/MinGW Python, check if we can find a standard Windows Python instead
if "%PYTHON_TYPE%"=="MINGW" (
  echo MSYS2/MinGW Python detected. Checking for standard Windows Python...
  
  REM Try to find standard Windows Python
  where py >nul 2>&1
  if %errorlevel% equ 0 (
    echo Found Python Launcher, using it instead
    set PYTHON_CMD=py
  ) else (
    REM Check common Python installation paths
    if exist "C:\Python311\python.exe" (
      echo Found Python in C:\Python311
      set "PYTHON_CMD=C:\Python311\python.exe"
    ) else if exist "C:\Program Files\Python311\python.exe" (
      echo Found Python in C:\Program Files\Python311
      set "PYTHON_CMD=C:\Program Files\Python311\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
      echo Found Python in %LOCALAPPDATA%\Programs\Python\Python311
      set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) else (
      echo Warning: Using MSYS2/MinGW Python as no standard Windows Python was found
      set PYTHON_CMD=python
    )
  )
) else (
  set PYTHON_CMD=python
)

echo Using Python command: %PYTHON_CMD%
%PYTHON_CMD% --version

REM Ensure virtual environment exists
if not exist "venv\" (
  echo Creating virtual environment...
  %PYTHON_CMD% -m venv venv
  if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment.
    echo Please check your Python installation and try again.
    
    REM If using MINGW, try installing venv module
    if "%PYTHON_TYPE%"=="MINGW" (
      echo Attempting to fix MSYS2/MinGW Python setup...
      echo You may need to run: pacman -S mingw-w64-x86_64-python-pip mingw-w64-x86_64-python-virtualenv
      echo Then try running this script again.
    )
    
    pause
    exit /b 1
  )
)

REM Activate virtual environment - try different approaches
echo Activating virtual environment...
if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate" (
  call venv\Scripts\activate
) else if exist "venv\bin\activate" (
  echo WARNING: Found non-standard venv structure, trying alternative activation...
  REM Set environment variables directly as fallback
  set "VIRTUAL_ENV=%CD%\venv"
  if "%PYTHON_TYPE%"=="MINGW" (
    set "PATH=%VIRTUAL_ENV%\bin;%PATH%"
  ) else (
    set "PATH=%VIRTUAL_ENV%\Scripts;%PATH%"
  )
  echo Using direct environment variable setup
  goto activation_complete
) else (
  echo ERROR: Could not find any activation script for this Python environment.
  echo Virtual environment may have an unexpected structure.
  pause
  exit /b 1
)

if %errorlevel% neq 0 (
  echo ERROR: Failed to activate virtual environment.
  echo The virtual environment might be corrupted.
  echo Try deleting the venv folder and running the script again.
  pause
  exit /b 1
)

:activation_complete
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

REM Check if pip is available
%PYTHON_CMD% -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
  echo ERROR: pip is not available in this Python installation.
  
  if "%PYTHON_TYPE%"=="MINGW" (
    echo For MSYS2/MinGW Python, try running these commands in MSYS2 terminal:
    echo pacman -S mingw-w64-x86_64-python-pip
    echo pacman -S mingw-w64-x86_64-python-setuptools
  ) else (
    echo Try running: %PYTHON_CMD% -m ensurepip
    echo Or download get-pip.py from https://bootstrap.pypa.io/get-pip.py
    echo and run: %PYTHON_CMD% get-pip.py
  )
  
  pause
  exit /b 1
)

echo Upgrading pip...
%PYTHON_CMD% -m pip install --upgrade pip
if %errorlevel% neq 0 (
  echo WARNING: Failed to upgrade pip, but continuing with installation...
)

echo Installing required packages...
%PYTHON_CMD% -m pip install flask werkzeug flask_limiter flask_wtf openpyxl requests
if %errorlevel% neq 0 (
  echo ERROR: Failed to install dependencies.
  pause
  exit /b 1
)
echo. > venv\.dependencies_installed
echo Dependencies installed successfully.

:after_install

REM Run test system if requested
if "%1"=="test" (
  echo Running test system...
  %PYTHON_CMD% test_system.py
  exit /b %errorlevel%
)

REM Default: Run the application
echo Starting Exam System...
echo Access the application at http://localhost:5000
echo Default teacher login: username=teacher, password=admin123
echo Press Ctrl+C to stop the server
%PYTHON_CMD% app.py

REM Keep the terminal open if there was an error
if %errorlevel% neq 0 (
  echo Press Enter to exit...
  pause > nul
)

exit /b %errorlevel%