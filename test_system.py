#!/usr/bin/env python3
"""
Test script for Exam System
This script performs basic checks to ensure the system is properly set up
"""

import os
import sys
import sqlite3
import importlib.util
import argparse
import socket
import time
import subprocess
import threading
from contextlib import closing


# ANSI color codes for better console output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
ENDC = '\033[0m'


def success(msg):
    """Print a success message"""
    print(f"{GREEN}✓ {msg}{ENDC}")


def error(msg):
    """Print an error message"""
    print(f"{RED}❌ Error: {msg}{ENDC}")


def warning(msg):
    """Print a warning message"""
    print(f"{YELLOW}⚠ Warning: {msg}{ENDC}")


def info(msg):
    """Print an info message"""
    print(f"{BLUE}ℹ {msg}{ENDC}")


def ensure_venv():
    """Ensure we're running inside the virtual environment, activate if not"""
    venv_path = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'venv')

    # Check if we're already in a virtual environment
    if sys.prefix != sys.base_prefix:
        success("Already running in virtual environment")
        return True

    # Check if venv exists
    if not os.path.exists(venv_path):
        warning("Virtual environment not found. Creating one...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            success("Created virtual environment")
        except subprocess.CalledProcessError:
            error("Failed to create virtual environment")
            return False

    # Try to activate the virtual environment
    if sys.platform == 'win32':
        venv_python = os.path.join(venv_path, 'Scripts', 'python.exe')
    else:
        venv_python = os.path.join(venv_path, 'bin', 'python')

    if not os.path.exists(venv_python):
        error(f"Virtual environment Python not found at {venv_python}")
        return False

    # Re-execute the current script with the venv python
    if sys.executable != venv_python:
        info(f"Activating virtual environment and restarting...")
        os.execl(venv_python, venv_python, *sys.argv)

    return True


def check_python_version():
    """Check if Python version is compatible"""
    print("Checking Python version...")
    if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
        error("Python 3.6 or higher is required")
        return False
    success(
        f"Python version {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} is compatible")
    return True


def check_dependencies():
    """Check if required packages are installed"""
    print("Checking dependencies...")
    dependencies = [
        'flask', 'werkzeug', 'sqlite3', 'hashlib',
        'datetime', 'json', 'random', 'secrets'
    ]
    missing = []
    warnings = []

    for package in dependencies:
        try:
            if importlib.util.find_spec(package) is None:
                # Some packages are built-in to Python and won't be found this way
                if package in ['sqlite3', 'hashlib', 'datetime', 'json', 'random', 'secrets']:
                    try:
                        __import__(package)
                    except ImportError:
                        missing.append(package)
                else:
                    missing.append(package)
        except ImportError:
            warnings.append(package)

    # Check for optional but recommended packages
    optional_packages = ['flask_limiter', 'flask_wtf']
    missing_optional = []

    for package in optional_packages:
        if importlib.util.find_spec(package) is None:
            missing_optional.append(package)

    if missing:
        error(f"Missing required packages: {', '.join(missing)}")
        print("Please install them using: pip install " + " ".join(missing))
        return False
    else:
        success("All required packages are installed")

    if missing_optional:
        warning(f"Missing optional packages: {', '.join(missing_optional)}")
        print("Consider installing them for better functionality: pip install " +
              " ".join(missing_optional))

    if warnings:
        warning(f"Couldn't verify these packages: {', '.join(warnings)}")

    return True


def check_file_structure():
    """Check if required files and folders exist"""
    print("Checking file structure...")
    required_files = ['app.py', 'static/css/style.css']
    required_dirs = ['templates', 'static',
                     'static/css', 'database', 'static/js']

    missing_files = [f for f in required_files if not os.path.isfile(f)]
    missing_dirs = [d for d in required_dirs if not os.path.isdir(d)]

    if missing_files or missing_dirs:
        if missing_files:
            error(f"Missing required files: {', '.join(missing_files)}")
        if missing_dirs:
            error(f"Missing required directories: {', '.join(missing_dirs)}")
        return False
    else:
        success("All required files and directories exist")
        return True


def check_templates():
    """Check if required template files exist"""
    print("Checking template files...")
    required_templates = [
        'base.html', 'login.html', 'student_login.html', 'exam.html',
        'create_exam.html', 'submissions.html', 'grade.html',
        'teacher_dashboard.html', 'admin_grades.html', 'ip_management.html'
    ]

    template_dir = 'templates'
    if not os.path.isdir(template_dir):
        error(f"Templates directory not found at '{template_dir}'")
        return False

    missing_templates = []
    for template in required_templates:
        if not os.path.isfile(os.path.join(template_dir, template)):
            missing_templates.append(template)

    if missing_templates:
        error(
            f"Missing required template files: {', '.join(missing_templates)}")
        return False
    else:
        success("All required template files exist")
        return True


def check_permissions():
    """Check if files have the correct permissions"""
    print("Checking file permissions...")

    # Files that should be executable
    executables = ['app.py', 'test_system.py']
    permission_issues = []

    for exe in executables:
        if os.path.isfile(exe):
            if not os.access(exe, os.X_OK):
                permission_issues.append(f"{exe} is not executable")

    # Check if database directory is writable
    if os.path.isdir('database') and not os.access('database', os.W_OK):
        permission_issues.append("database directory is not writable")

    if permission_issues:
        warning("Permission issues found:")
        for issue in permission_issues:
            print(f"  - {issue}")
        print("You can fix permissions with 'chmod +x filename' for executables")
        return False
    else:
        success("File permissions look good")
        return True


def check_database():
    """Check if database is properly initialized"""
    print("Checking database...")
    db_path = 'database/exam_system.db'

    # Create database directory if it doesn't exist
    os.makedirs('database', exist_ok=True)

    try:
        # Initialize database if it doesn't exist
        if not os.path.exists(db_path):
            info("Database file doesn't exist. Attempting to initialize...")
            spec = importlib.util.spec_from_file_location("app", "./app.py")
            app_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app_module)

            if os.path.exists(db_path):
                success("Database initialized successfully")
            else:
                error("Failed to initialize database")
                return False

        # Check if database can be opened and tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check for required tables
        required_tables = [
            'users', 'exams', 'questions', 'submissions',
            'ip_restrictions', 'exam_sessions', 'grades'
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        missing_tables = [
            table for table in required_tables if table not in tables]

        if missing_tables:
            error(
                f"Missing required tables in database: {', '.join(missing_tables)}")
            return False
        else:
            success("Database schema is properly initialized")
            return True

    except Exception as e:
        error(f"Error checking database: {str(e)}")
        return False


def is_port_in_use(port):
    """Check if a port is in use"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(('localhost', port)) == 0


def start_test_server():
    """Start a test server in the background"""
    if os.path.exists('app.py'):
        return subprocess.Popen(
            [sys.executable, 'app.py', '--test-mode'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    return None


def test_server_connection():
    """Test if server can start and accept connections"""
    print("Testing server connection...")

    # Check if port 5000 is already in use
    if is_port_in_use(5000):
        warning("Port 5000 is already in use. Skipping server connection test.")
        info("To manually test, run 'python app.py' and access http://localhost:5000")
        return True

    # Start server in a background process
    server_process = start_test_server()
    if not server_process:
        error("Could not start test server (app.py not found)")
        return False

    # Give the server a moment to start
    time.sleep(2)

    try:
        # Try to connect to the server
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            result = sock.connect_ex(('localhost', 5000))
            if result == 0:
                success("Server started successfully and is accepting connections")
                connected = True
            else:
                error("Could not connect to server on port 5000")
                connected = False
    except Exception as e:
        error(f"Error testing server connection: {str(e)}")
        connected = False

    # Terminate the server process
    if server_process:
        server_process.terminate()
        server_process.wait(timeout=5)

    return connected


def main():
    """Main function to run tests"""
    parser = argparse.ArgumentParser(description='Exam System Test Utility')
    parser.add_argument('-t', '--test', choices=[
        'python', 'dependencies', 'files', 'templates',
        'permissions', 'database', 'server', 'all'
    ], default='all', help='Specific test to run (default: all)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Print only errors and summary')

    args = parser.parse_args()

    if not args.quiet:
        print(f"{BLUE}Exam System Test Utility{ENDC}")
        print(f"{BLUE}------------------------{ENDC}")

    # Ensure virtual environment is activated
    if not ensure_venv():
        return 1

    # Map command line options to test functions
    test_map = {
        'python': check_python_version,
        'dependencies': check_dependencies,
        'files': check_file_structure,
        'templates': check_templates,
        'permissions': check_permissions,
        'database': check_database,
        'server': test_server_connection
    }

    # Determine which tests to run
    if args.test == 'all':
        tests = list(test_map.values())
    else:
        tests = [test_map[args.test]]

    results = []
    for test in tests:
        results.append(test())

    print(f"\n{BLUE}Test Summary{ENDC}")
    print(f"{BLUE}-----------{ENDC}")
    passed = results.count(True)
    total = len(results)
    print(f"Passed: {passed}/{total} tests")

    if all(results):
        print(
            f"\n{GREEN}✓ All tests passed! Your Exam System should work correctly.{ENDC}")
        print(
            f"{BLUE}Start the server with 'python app.py' and access it at http://localhost:5000{ENDC}")
    else:
        print(
            f"\n{RED}❌ Some tests failed. Please fix the issues mentioned above.{ENDC}")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
