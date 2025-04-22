#!/bin/bash
# Helper script to run the Exam System with the virtual environment properly activated
# Usage:
#   ./run.sh           - Run the application
#   ./run.sh test      - Run the test system
#   ./run.sh install   - Install dependencies
#   ./run.sh help      - Show this help message

# Set the script to exit immediately if a command exits with a non-zero status
set -e

# Directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Make sure the script is executable
if [ ! -x "$0" ]; then
  chmod +x "$0"
  echo "Made run.sh executable."
fi

# Ensure virtual environment exists
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate
echo "Virtual environment activated."

# Install dependencies if requested or if first run
if [ "$1" == "install" ] || [ ! -f "venv/.dependencies_installed" ]; then
  echo "Installing dependencies..."
  pip install flask werkzeug flask_limiter flask_wtf openpyxl requests
  touch venv/.dependencies_installed
  echo "Dependencies installed successfully."
fi

# Show help if requested
if [ "$1" == "help" ]; then
  echo "Exam System Helper Script"
  echo "------------------------"
  echo "Usage:"
  echo "  ./run.sh           - Run the application"
  echo "  ./run.sh test      - Run the test system"
  echo "  ./run.sh install   - Install dependencies"
  echo "  ./run.sh help      - Show this help message"
  exit 0
fi

# Run test system if requested
if [ "$1" == "test" ]; then
  echo "Running test system..."
  python test_system.py
  exit $?
fi

# Default: Run the application
echo "Starting Exam System..."
python app.py

# Keep the terminal open if there was an error
if [ $? -ne 0 ]; then
  echo "Press Enter to exit..."
  read
fi