# Exam System

A lightweight SQL exam system designed for offline use in educational environments.

## Features

### For Students:

- Take exams with a server-side timer (not affected by page refreshes)
- SQL code editor with syntax highlighting
- Automatic submission every 10 minutes
- IP address tracking for security

### For Teachers:

- Create and manage exams with custom questions and duration
- Review student submissions (up to 3-4 versions saved)
- Grade submissions with comments and marks
- Manage IP restrictions (approve/block student access)

## Setup & Running Instructions

### Linux Setup

The easiest way to set up and run the system on Linux is using the provided run script:

```bash
chmod +x run.sh
./run.sh
```

This script will:

1. Create a virtual environment if it doesn't exist
2. Install all required dependencies
3. Create necessary directories
4. Start the application

Additional commands:

```bash
./run.sh install   # Force reinstall dependencies
./run.sh test      # Run the test system
./run.sh help      # Show help message
```

### Windows Setup

The easiest way to set up and run the system on Windows is using the provided run script:

Simply double-click `run.bat` or run it from Command Prompt:

```cmd
run.bat
```

This script will:

1. Create a virtual environment if it doesn't exist
2. Install all required dependencies
3. Create necessary directories
4. Start the application

Additional commands:

```cmd
run.bat install    # Force reinstall dependencies
run.bat test       # Run the test system
run.bat help       # Show help message
```

### Manual Setup (if scripts don't work)

#### Manual Setup for Linux

1. Create a virtual environment

```bash
cd /home/john/ES
python -m venv venv
```

2. Activate the virtual environment

```bash
source venv/bin/activate
```

3. Install required packages

```bash
pip install flask werkzeug flask_limiter flask_wtf openpyxl
```

4. Create database directory

```bash
mkdir -p database
```

5. Run the application

```bash
python app.py
```

#### Manual Setup for Windows

1. Open Command Prompt and navigate to the project directory:

```cmd
cd path\to\ES
```

2. Create a virtual environment

```cmd
python -m venv venv
```

3. Activate the virtual environment

```cmd
venv\Scripts\activate.bat
```

4. Install required packages

```cmd
pip install flask werkzeug flask_limiter flask_wtf openpyxl
```

5. Create database directory

```cmd
mkdir database
```

6. Run the application

```cmd
python app.py
```

After setup, the system will be available at http://localhost:5000

## Testing the System

The Exam System comes with built-in testing utilities to verify proper setup and performance under load.

### System Test

The system test utility verifies that your environment is correctly set up and all components are working:

```bash
# Using the run script (Linux)
./run.sh test

# Using the run script (Windows)
run.bat test

# Or directly
python test_system.py
```

The test system checks:

- Python version compatibility
- Required dependencies
- File and folder structure
- Template files
- File permissions
- Database initialization
- Server connectivity

Additional test options:

```bash
# Test specific components
python test_system.py --test python
python test_system.py --test dependencies
python test_system.py --test files
python test_system.py --test templates
python test_system.py --test permissions
python test_system.py --test database
python test_system.py --test server

# Quiet mode (print only errors and summary)
python test_system.py --quiet
```

### Stress Test

The stress test utility simulates multiple concurrent students accessing, solving, and submitting exams to test how the system performs under load:

```bash
# Basic usage
python stress_test.py

# Advanced usage
python stress_test.py -n 200 -c 30 -a 5 -v
```

Parameters:

- `-n, --num-students N`: Number of students to simulate (default: 100)
- `-c, --concurrent N`: Maximum concurrent connections (default: 20)
- `-a, --auto-saves N`: Number of auto-saves per student (default: 3)
- `-v, --verbose`: Show detailed progress
- `--url URL`: Base URL of the exam system (default: http://localhost:5000)
- `--skip-check`: Skip checking for active exam

The test generates a JSON report with detailed metrics including:

- Total execution time
- Success rate
- Request timing statistics (login, exam loading, auto-saving, submission)
- Requests per second

For more details, see the `stress_test_README.md` file.

## Default Credentials

Teacher login:

- Username: `teacher`
- Password: `admin123`

Students don't need accounts - they log in with their name and student number.

## Usage Guide

### For Teachers:

1. Log in using teacher credentials
2. Create a new exam with questions
3. Activate the exam when ready for students
4. Students can now access the exam
5. Review and grade submissions after the exam
6. Manage IP restrictions as needed

### For Students:

1. Access the system at the URL provided by your teacher
2. Enter your name and student number
3. Complete the exam before the timer ends
4. Your work is auto-saved every 10 minutes
5. Submit when finished or wait for automatic submission when time expires

## Technical Details

- Server-side timer implementation ensures accurate timing regardless of client-side actions
- IP tracking prevents unauthorized access
- SQLite database for simple deployment with no additional database server
- Minimal dependencies for easy setup

## Troubleshooting

### Firewall Configuration

If you're having trouble connecting to the application, you may need to allow the application through your firewall:

#### Linux

```bash
sudo ufw allow 5000/tcp
```

#### Windows

1. Open Windows Defender Firewall with Advanced Security (search for it in the Start menu)
2. Click on "Inbound Rules" on the left panel
3. Click on "New Rule..." on the right panel
4. Select "Port" and click Next
5. Select "TCP" and enter "5000" in the "Specific local ports" field, then click Next
6. Select "Allow the connection" and click Next
7. Select the networks where the rule applies (Domain, Private, Public) and click Next
8. Give the rule a name (e.g., "Flask Exam System") and click Finish

Alternatively, you can use Command Prompt with admin privileges:

```cmd
netsh advfirewall firewall add rule name="Flask Exam System" dir=in action=allow protocol=TCP localport=5000
```
