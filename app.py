import os
import time
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database setup
DATABASE_PATH = 'database/exam_system.db'


def init_db():
    """Initialize database with required tables"""
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
        ''')

        # Create exams table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            duration INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT 0,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # Create questions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            exam_id INTEGER,
            question_text TEXT NOT NULL,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
        ''')

        # Create submissions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            student_name TEXT NOT NULL,
            student_number TEXT NOT NULL,
            exam_id INTEGER,
            submission_time TIMESTAMP,
            ip_address TEXT,
            code_content TEXT,
            version INTEGER,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
        ''')

        # Create question_answers table for individual answers per question
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS question_answers (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER,
            question_id INTEGER,
            answer_content TEXT,
            FOREIGN KEY (submission_id) REFERENCES submissions (id),
            FOREIGN KEY (question_id) REFERENCES questions (id)
        )
        ''')

        # Create ip_restrictions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_restrictions (
            id INTEGER PRIMARY KEY,
            ip_address TEXT NOT NULL UNIQUE,
            is_blocked BOOLEAN DEFAULT 0,
            blocked_time TIMESTAMP,
            approved BOOLEAN DEFAULT 0
        )
        ''')

        # Create exam_sessions table for tracking active exams
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_sessions (
            id INTEGER PRIMARY KEY,
            student_name TEXT NOT NULL,
            student_number TEXT NOT NULL,
            exam_id INTEGER,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            ip_address TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
        ''')

        # Create grades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER,
            mark FLOAT,
            comment TEXT,
            graded_by INTEGER,
            graded_at TIMESTAMP,
            FOREIGN KEY (submission_id) REFERENCES submissions (id),
            FOREIGN KEY (graded_by) REFERENCES users (id)
        )
        ''')

        # Insert default teacher account if not exists
        cursor.execute("SELECT * FROM users WHERE username = 'teacher'")
        if not cursor.fetchone():
            teacher_password = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('teacher', teacher_password, 'teacher')
            )

        conn.commit()


# Ensure database directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
init_db()

# Login route


@app.route('/')
def login():
    # Redirect root URL to the student login page
    return redirect(url_for('student_login'))


@app.route('/teacher_login', methods=['GET', 'POST'])
def teacher_login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[3]

                if user[3] == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                else:
                    return redirect(url_for('student_login'))
            else:
                error = 'Invalid credentials'

    return render_template('login.html', error=error)

# Student login route (separate from teacher login)


@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    error = None
    if request.method == 'POST':
        name = request.form['name']
        student_number = request.form['student_number']
        exam_id = request.form.get('exam_id')

        if not name or not student_number:
            error = 'Please enter both name and student number'
            return render_template('student_login.html', error=error)

        # Check if an exam is active
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get active exam
            cursor.execute("SELECT * FROM exams WHERE is_active = 1")
            exam = cursor.fetchone()

            if not exam:
                error = 'No active exam available'
                return render_template('student_login.html', error=error)

            # Check IP address
            ip_address = request.remote_addr
            cursor.execute(
                "SELECT * FROM ip_restrictions WHERE ip_address = ?", (ip_address,))
            ip_restriction = cursor.fetchone()

            if ip_restriction and ip_restriction['is_blocked'] and not ip_restriction['approved']:
                error = 'Your IP address is blocked. Please contact the teacher.'
                return render_template('student_login.html', error=error)

            # Check for existing session
            cursor.execute(
                """
                SELECT * FROM exam_sessions 
                WHERE student_number = ? AND exam_id = ? AND end_time > ?
                """,
                (student_number, exam['id'], datetime.now())
            )
            existing_session = cursor.fetchone()

            if not existing_session:
                # Create new exam session
                start_time = datetime.now()
                end_time = start_time + timedelta(minutes=exam['duration'])

                cursor.execute(
                    """
                    INSERT INTO exam_sessions 
                    (student_name, student_number, exam_id, start_time, end_time, ip_address) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, student_number, exam['id'],
                     start_time, end_time, ip_address)
                )
                session_id = cursor.lastrowid
            else:
                session_id = existing_session['id']

            session['student_name'] = name
            session['student_number'] = student_number
            session['exam_id'] = exam['id']
            session['session_id'] = session_id

            # Record IP address
            if not ip_restriction:
                cursor.execute(
                    "INSERT INTO ip_restrictions (ip_address, is_blocked, approved) VALUES (?, 0, 1)",
                    (ip_address,)
                )

            return redirect(url_for('take_exam'))

    return render_template('student_login.html', error=error)

# Student exam page


@app.route('/take_exam')
def take_exam():
    if 'student_name' not in session or 'student_number' not in session or 'exam_id' not in session:
        return redirect(url_for('student_login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get exam details
        cursor.execute("SELECT * FROM exams WHERE id = ?",
                       (session['exam_id'],))
        exam = cursor.fetchone()

        # Get exam questions
        cursor.execute("SELECT * FROM questions WHERE exam_id = ?",
                       (session['exam_id'],))
        questions = cursor.fetchall()

        # Get student's session info
        cursor.execute("SELECT * FROM exam_sessions WHERE id = ?",
                       (session['session_id'],))
        exam_session = cursor.fetchone()

        if not exam_session:
            return redirect(url_for('student_login'))

        end_time = exam_session['end_time']
        remaining_seconds = max(0, (datetime.fromisoformat(
            end_time) - datetime.now()).total_seconds())

        # Get previous submission if exists
        cursor.execute(
            """
            SELECT * FROM submissions 
            WHERE student_number = ? AND exam_id = ? 
            ORDER BY submission_time DESC LIMIT 1
            """,
            (session['student_number'], session['exam_id'])
        )
        submission = cursor.fetchone()

        # Initialize with empty answers
        answers = {}
        for question in questions:
            answers[question['id']] = ""

        # If submission exists, get the answers for each question
        if submission:
            # For backwards compatibility, store the old full submission
            prev_code = submission['code_content']

            # Get individual answers for each question
            cursor.execute(
                """
                SELECT question_id, answer_content FROM question_answers
                WHERE submission_id = ?
                """,
                (submission['id'],)
            )
            question_answers = cursor.fetchall()

            for answer in question_answers:
                answers[answer['question_id']] = answer['answer_content']
        else:
            prev_code = ""

        return render_template(
            'exam.html',
            exam=exam,
            questions=questions,
            remaining_seconds=int(remaining_seconds),
            prev_code=prev_code,
            answers=answers
        )

# Auto-save submission API endpoint


@app.route('/api/auto_save', methods=['POST'])
def auto_save():
    if 'student_name' not in session or 'student_number' not in session or 'exam_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    answers = request.json.get('answers', {})  # Get answers for each question
    combined_code = request.json.get(
        'combinedCode', '')  # For backward compatibility
    ip_address = request.remote_addr

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get most recent version number
        cursor.execute(
            """
            SELECT MAX(version) as max_version FROM submissions 
            WHERE student_number = ? AND exam_id = ?
            """,
            (session['student_number'], session['exam_id'])
        )
        result = cursor.fetchone()
        new_version = (result[0] or 0) + 1

        # Delete old versions if more than 4
        if new_version > 4:
            cursor.execute(
                """
                DELETE FROM submissions 
                WHERE student_number = ? AND exam_id = ? 
                ORDER BY submission_time ASC LIMIT 1
                """,
                (session['student_number'], session['exam_id'])
            )

        # Insert new submission
        cursor.execute(
            """
            INSERT INTO submissions 
            (student_name, student_number, exam_id, submission_time, ip_address, code_content, version) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session['student_name'],
                session['student_number'],
                session['exam_id'],
                datetime.now(),
                ip_address,
                combined_code,
                new_version
            )
        )
        submission_id = cursor.lastrowid

        # Save individual answers for each question
        for question_id, answer_content in answers.items():
            cursor.execute(
                """
                INSERT INTO question_answers
                (submission_id, question_id, answer_content)
                VALUES (?, ?, ?)
                """,
                (submission_id, question_id, answer_content)
            )

        conn.commit()
        return jsonify({'success': True, 'version': new_version})

# Final submission endpoint


@app.route('/api/submit', methods=['POST'])
def submit_exam():
    if 'student_name' not in session or 'student_number' not in session or 'exam_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    answers = request.json.get('answers', {})  # Get answers for each question
    combined_code = request.json.get(
        'combinedCode', '')  # For backward compatibility
    ip_address = request.remote_addr

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Get most recent version number
        cursor.execute(
            """
            SELECT MAX(version) as max_version FROM submissions 
            WHERE student_number = ? AND exam_id = ?
            """,
            (session['student_number'], session['exam_id'])
        )
        result = cursor.fetchone()
        new_version = (result[0] or 0) + 1

        # Insert final submission
        cursor.execute(
            """
            INSERT INTO submissions 
            (student_name, student_number, exam_id, submission_time, ip_address, code_content, version) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session['student_name'],
                session['student_number'],
                session['exam_id'],
                datetime.now(),
                ip_address,
                combined_code,
                new_version
            )
        )
        submission_id = cursor.lastrowid

        # Save individual answers for each question
        for question_id, answer_content in answers.items():
            cursor.execute(
                """
                INSERT INTO question_answers
                (submission_id, question_id, answer_content)
                VALUES (?, ?, ?)
                """,
                (submission_id, question_id, answer_content)
            )

        # Block IP after submission
        cursor.execute(
            """
            UPDATE ip_restrictions 
            SET is_blocked = 1, blocked_time = ?, approved = 0 
            WHERE ip_address = ?
            """,
            (datetime.now(), ip_address)
        )

        # Clear session
        session.pop('student_name', None)
        session.pop('student_number', None)
        session.pop('exam_id', None)
        session.pop('session_id', None)

        conn.commit()
        return jsonify({'success': True})

# Teacher dashboard route


@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exams ORDER BY id DESC")
        exams = cursor.fetchall()

    return render_template('teacher_dashboard.html', exams=exams)

# Create exam route


@app.route('/teacher/create_exam', methods=['GET', 'POST'])
def create_exam():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        duration = int(request.form['duration'])
        questions = request.form.getlist('question')

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Insert exam
            cursor.execute(
                "INSERT INTO exams (title, duration, created_by) VALUES (?, ?, ?)",
                (title, duration, session['user_id'])
            )
            exam_id = cursor.lastrowid

            # Insert questions
            for question in questions:
                if question.strip():
                    cursor.execute(
                        "INSERT INTO questions (exam_id, question_text) VALUES (?, ?)",
                        (exam_id, question)
                    )

            conn.commit()

        return redirect(url_for('teacher_dashboard'))

    return render_template('create_exam.html')

# Activate exam route


@app.route('/teacher/activate_exam/<int:exam_id>')
def activate_exam(exam_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Deactivate all exams
        cursor.execute("UPDATE exams SET is_active = 0")

        # Activate selected exam
        cursor.execute(
            "UPDATE exams SET is_active = 1 WHERE id = ?", (exam_id,))

        conn.commit()

    return redirect(url_for('teacher_dashboard'))

# View submissions route


@app.route('/teacher/submissions/<int:exam_id>')
def view_submissions(exam_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get exam details
        cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        exam = cursor.fetchone()

        # Get all unique students who submitted
        cursor.execute(
            """
            SELECT DISTINCT student_name, student_number, ip_address 
            FROM submissions 
            WHERE exam_id = ?
            """,
            (exam_id,)
        )
        students = cursor.fetchall()

        # Get latest submissions for each student (up to 3)
        student_submissions = {}
        for student in students:
            cursor.execute(
                """
                SELECT * FROM submissions 
                WHERE student_number = ? AND exam_id = ? 
                ORDER BY submission_time DESC LIMIT 3
                """,
                (student['student_number'], exam_id)
            )
            submissions = cursor.fetchall()

            # Mark the first one (most recent) as the latest
            if submissions:
                # Convert submissions to list to allow modifications
                submissions_list = []
                for i, sub in enumerate(submissions):
                    # Convert Row to dict
                    sub_dict = dict(sub)
                    # Add is_latest flag
                    # Only the first (most recent) is latest
                    sub_dict['is_latest'] = (i == 0)
                    submissions_list.append(sub_dict)

                student_submissions[student['student_number']
                                    ] = submissions_list
            else:
                student_submissions[student['student_number']] = []

    return render_template(
        'submissions.html',
        exam=exam,
        students=students,
        student_submissions=student_submissions
    )

# Grade submission route


@app.route('/teacher/grade/<int:submission_id>', methods=['GET', 'POST'])
def grade_submission(submission_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get submission details
        cursor.execute("SELECT * FROM submissions WHERE id = ?",
                       (submission_id,))
        submission = cursor.fetchone()

        if not submission:
            return redirect(url_for('teacher_dashboard'))

        # Check if this is the latest submission for this student/exam
        cursor.execute(
            """
            SELECT id FROM submissions 
            WHERE student_number = ? AND exam_id = ? 
            ORDER BY submission_time DESC LIMIT 1
            """,
            (submission['student_number'], submission['exam_id'])
        )
        latest_submission = cursor.fetchone()
        is_latest = latest_submission and latest_submission['id'] == submission_id

        # For POST requests (when submitting a grade)
        if request.method == 'POST':
            # Only allow grading if this is the latest submission
            if not is_latest:
                return render_template(
                    'grade.html',
                    submission=submission,
                    error_message="Only the latest submission can be graded. This is not the latest submission.",
                    is_latest=is_latest,
                    can_grade=False
                )

            mark = float(request.form['mark'])
            comment = request.form['comment']

            # Check if grade already exists
            cursor.execute(
                "SELECT * FROM grades WHERE submission_id = ?", (submission_id,))
            existing_grade = cursor.fetchone()

            if existing_grade:
                cursor.execute(
                    """
                    UPDATE grades 
                    SET mark = ?, comment = ?, graded_by = ?, graded_at = ? 
                    WHERE submission_id = ?
                    """,
                    (mark, comment, session['user_id'],
                     datetime.now(), submission_id)
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO grades 
                    (submission_id, mark, comment, graded_by, graded_at) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (submission_id, mark, comment,
                     session['user_id'], datetime.now())
                )

            return redirect(url_for('view_submissions', exam_id=submission['exam_id']))

        # Get existing grade if any
        cursor.execute(
            "SELECT * FROM grades WHERE submission_id = ?", (submission_id,))
        grade = cursor.fetchone()

        # Get exam questions
        cursor.execute("SELECT * FROM questions WHERE exam_id = ?",
                       (submission['exam_id'],))
        questions = cursor.fetchall()

        # Get individual question answers
        cursor.execute(
            """
            SELECT question_id, answer_content FROM question_answers
            WHERE submission_id = ?
            """,
            (submission_id,)
        )
        question_answers_rows = cursor.fetchall()

        # Convert to dictionary for easier access in template
        question_answers = {}
        for row in question_answers_rows:
            question_answers[row['question_id']] = row['answer_content']

    return render_template(
        'grade.html',
        submission=submission,
        grade=grade,
        questions=questions,
        question_answers=question_answers,
        is_latest=is_latest,
        can_grade=is_latest
    )

# IP management route


@app.route('/teacher/ip_management')
def ip_management():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ip_restrictions ORDER BY id DESC")
        ip_restrictions = cursor.fetchall()

    return render_template('ip_management.html', ip_restrictions=ip_restrictions)

# Approve IP route


@app.route('/teacher/approve_ip/<int:ip_id>')
def approve_ip(ip_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ip_restrictions SET is_blocked = 0, approved = 1 WHERE id = ?",
            (ip_id,)
        )
        conn.commit()

    return redirect(url_for('ip_management'))

# Block IP route


@app.route('/teacher/block_ip/<int:ip_id>')
def block_ip(ip_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ip_restrictions SET is_blocked = 1, blocked_time = ?, approved = 0 WHERE id = ?",
            (datetime.now(), ip_id)
        )
        conn.commit()

    return redirect(url_for('ip_management'))

# View all student grades route


@app.route('/teacher/all_grades')
def all_grades():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all exams
        cursor.execute("SELECT * FROM exams ORDER BY id DESC")
        exams = cursor.fetchall()

        # Get all students who have submissions
        cursor.execute(
            """
            SELECT DISTINCT student_name, student_number 
            FROM submissions 
            ORDER BY student_name
            """
        )
        students = cursor.fetchall()

        # Get grades only from the latest submissions for each student/exam
        cursor.execute(
            """
            WITH latest_submissions AS (
                SELECT s.id, s.student_number, s.exam_id, s.student_name,
                       ROW_NUMBER() OVER (PARTITION BY s.student_number, s.exam_id 
                                         ORDER BY s.submission_time DESC) AS submission_rank
                FROM submissions s
            )
            SELECT g.*, ls.student_name, ls.student_number, ls.exam_id, e.title as exam_title
            FROM grades g
            JOIN latest_submissions ls ON g.submission_id = ls.id AND ls.submission_rank = 1
            JOIN exams e ON ls.exam_id = e.id
            ORDER BY e.id DESC, ls.student_name ASC
            """
        )
        all_grades = cursor.fetchall()

        # Organize grades by exam and student for easier display
        grades_by_exam = {}
        for exam in exams:
            grades_by_exam[exam['id']] = {
                'exam_title': exam['title'],
                'students': {}
            }

        for grade in all_grades:
            exam_id = grade['exam_id']
            student_number = grade['student_number']

            if exam_id in grades_by_exam:
                if student_number not in grades_by_exam[exam_id]['students']:
                    grades_by_exam[exam_id]['students'][student_number] = {
                        'student_name': grade['student_name'],
                        'student_number': student_number,
                        'grade': grade['mark'],
                        'comment': grade['comment']
                    }

        # Get list of students who haven't been graded for each exam (only check latest submissions)
        # Now include the submission id for direct linking
        ungraded_students = {}
        for exam in exams:
            cursor.execute(
                """
                WITH latest_submissions AS (
                    SELECT s.id, s.student_name, s.student_number,
                           ROW_NUMBER() OVER (PARTITION BY s.student_number, s.exam_id 
                                             ORDER BY s.submission_time DESC) AS submission_rank
                    FROM submissions s
                    WHERE s.exam_id = ?
                )
                SELECT ls.id as submission_id, ls.student_name, ls.student_number
                FROM latest_submissions ls
                LEFT JOIN grades g ON g.submission_id = ls.id
                WHERE ls.submission_rank = 1 AND g.id IS NULL
                ORDER BY ls.student_name
                """,
                (exam['id'],)
            )
            ungraded_students[exam['id']] = cursor.fetchall()

    return render_template(
        'admin_grades.html',
        exams=exams,
        students=students,
        grades_by_exam=grades_by_exam,
        ungraded_students=ungraded_students
    )

# Export grades to Excel route


@app.route('/teacher/export_grades')
def export_grades():
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all exams
        cursor.execute("SELECT * FROM exams ORDER BY id DESC")
        exams = cursor.fetchall()

        # Get grades only from the latest submissions for each student/exam
        cursor.execute(
            """
            WITH latest_submissions AS (
                SELECT s.id, s.student_number, s.exam_id, s.student_name,
                       ROW_NUMBER() OVER (PARTITION BY s.student_number, s.exam_id 
                                         ORDER BY s.submission_time DESC) AS submission_rank
                FROM submissions s
            )
            SELECT g.*, ls.student_name, ls.student_number, ls.exam_id, e.title as exam_title
            FROM grades g
            JOIN latest_submissions ls ON g.submission_id = ls.id AND ls.submission_rank = 1
            JOIN exams e ON ls.exam_id = e.id
            ORDER BY e.id DESC, ls.student_name ASC
            """
        )
        all_grades = cursor.fetchall()

    # Create an Excel workbook and sheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Grades"

    # Define styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4F81BD")
    header_alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    # Write header
    headers = ["Exam Title", "Student Name",
               "Student Number", "Grade", "Comment"]
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Write data
    for row_num, grade in enumerate(all_grades, 2):
        ws.cell(row=row_num, column=1,
                value=grade['exam_title']).border = thin_border
        ws.cell(row=row_num, column=2,
                value=grade['student_name']).border = thin_border
        ws.cell(row=row_num, column=3,
                value=grade['student_number']).border = thin_border
        ws.cell(row=row_num, column=4,
                value=grade['mark']).border = thin_border
        ws.cell(row=row_num, column=5,
                value=grade['comment']).border = thin_border

    # Save the workbook to a BytesIO object
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # Send the file to the user
    return send_file(output, as_attachment=True, download_name="grades.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Export grades to Excel for a specific exam


@app.route('/teacher/export_grades/<int:exam_id>')
def export_grades_excel(exam_id):
    if 'role' not in session or session['role'] != 'teacher':
        return redirect(url_for('login'))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get exam details
        cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
        exam = cursor.fetchone()

        if not exam:
            return redirect(url_for('teacher_dashboard'))

        # Get all questions for this exam
        cursor.execute(
            "SELECT * FROM questions WHERE exam_id = ? ORDER BY id", (exam_id,))
        questions = cursor.fetchall()

        # Get grades only from the latest submissions for each student for this specific exam
        cursor.execute(
            """
            WITH latest_submissions AS (
                SELECT s.id, s.student_number, s.student_name, s.submission_time, s.ip_address,
                       ROW_NUMBER() OVER (PARTITION BY s.student_number 
                                         ORDER BY s.submission_time DESC) AS submission_rank
                FROM submissions s
                WHERE s.exam_id = ?
            )
            SELECT 
                ls.id AS submission_id,
                ls.student_name, 
                ls.student_number, 
                ls.submission_time,
                ls.ip_address,
                g.mark, 
                g.comment, 
                g.graded_at
            FROM latest_submissions ls
            LEFT JOIN grades g ON g.submission_id = ls.id
            WHERE ls.submission_rank = 1
            ORDER BY ls.student_name
            """,
            (exam_id,)
        )
        student_data = cursor.fetchall()

        # Create a workbook and add a worksheet
        wb = Workbook()
        ws = wb.active
        # Excel worksheet names are limited to 31 chars
        ws.title = exam['title'][:31]

        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        # Helwan University blue
        header_fill = PatternFill("solid", fgColor="183A64")
        header_alignment = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Write exam information
        ws.cell(row=1, column=1, value="Exam:").font = Font(bold=True)
        ws.cell(row=1, column=2, value=exam['title'])
        ws.cell(row=2, column=1, value="Duration (minutes):").font = Font(bold=True)
        ws.cell(row=2, column=2, value=exam['duration'])
        ws.cell(row=3, column=1, value="Export Date:").font = Font(bold=True)
        ws.cell(row=3, column=2, value=datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"))

        # Add some space
        current_row = 5

        # Write headers
        headers = ["Student Name", "Student Number",
                   "IP Address", "Submission Time", "Grade", "Comment"]

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border

        # Set column widths
        column_widths = [20, 15, 15, 20, 10, 30]
        for i, width in enumerate(column_widths):
            ws.column_dimensions[chr(65 + i)].width = width

        # Write student data
        for row_num, student in enumerate(student_data, current_row + 1):
            ws.cell(row=row_num, column=1,
                    value=student['student_name']).border = thin_border
            ws.cell(row=row_num, column=2,
                    value=student['student_number']).border = thin_border
            ws.cell(row=row_num, column=3,
                    value=student['ip_address']).border = thin_border
            ws.cell(row=row_num, column=4,
                    value=student['submission_time']).border = thin_border

            # Grade might be NULL if not graded yet
            grade_cell = ws.cell(
                row=row_num, column=5, value=student['mark'] if student['mark'] is not None else "Not graded")
            grade_cell.border = thin_border

            # If not graded, add red fill
            if student['mark'] is None:
                grade_cell.fill = PatternFill("solid", fgColor="FFCCCC")

            comment_cell = ws.cell(
                row=row_num, column=6, value=student['comment'] if student['comment'] is not None else "")
            comment_cell.border = thin_border

        # Save the workbook to a BytesIO object
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Generate a meaningful filename with the exam title and date
        safe_title = ''.join(
            c for c in exam['title'] if c.isalnum() or c in ' _-').strip()
        safe_title = safe_title.replace(' ', '_')
        filename = f"{safe_title}_grades_{datetime.now().strftime('%Y%m%d')}.xlsx"

        # Send the file to the user
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Logout route


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
