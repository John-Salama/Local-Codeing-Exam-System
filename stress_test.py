#!/usr/bin/env python3
"""
Stress Test for Helwan Exam System
This script simulates 100 concurrent students entering, solving, and submitting exams.
"""

import requests
import time
import random
import string
import concurrent.futures
import json
import re
import argparse
import sys
from datetime import datetime
import statistics
from requests.exceptions import ProxyError
import os

# Configuration
DEFAULT_URL = "http://localhost:5000"
DEFAULT_NUM_STUDENTS = 100
DEFAULT_CONCURRENT_STUDENTS = 20  # How many students to run in parallel at once
DEFAULT_AUTO_SAVES_PER_STUDENT = 3  # Number of auto-saves before final submission

# IP Rotation Configuration
USE_IP_ROTATION = True  # Set to False if you don't want to use IP rotation
FAKE_IP_HEADER = 'X-Forwarded-For'  # Header for sending custom IP

# Global statistics
stats = {
    "login_times": [],
    "exam_load_times": [],
    "auto_save_times": [],
    "submission_times": [],
    "total_times": [],
    "failed_requests": 0,
    "successful_students": 0,
    "models_assigned": {}  # Track which models are assigned to students
}

# ANSI color codes for better console output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
ENDC = '\033[0m'


def generate_student_data(index):
    """Generate random student data for testing"""
    return {
        'name': f"Test Student {index}",
        'student_number': f"ST{100000 + index}"
    }


def generate_random_answers(num_questions, length=50, student_index=0, revision=0):
    """Generate random answers for each question"""
    answers = {}
    for i in range(1, num_questions + 1):
        # Generate a random string as the answer with the specified format
        revision_text = f" (revision {revision})" if revision > 0 else ""
        answers[str(
            i)] = f"Answer from student {student_index} to question {i}{revision_text}"
    return answers


def generate_random_ip():
    """Generate a random IP address"""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 255)}"


def extract_questions_from_html(html_content):
    """Extract question IDs from the exam HTML page"""
    # Use regex to find question IDs in data-question-id attributes
    question_ids = re.findall(r'data-question-id="(\d+)"', html_content)

    # If that fails, try an alternative approach by looking for question panels
    if not question_ids:
        question_ids = re.findall(r'id="question-panel-(\d+)"', html_content)

    # Convert to integers and return
    return [int(qid) for qid in question_ids]


def extract_model_from_html(html_content):
    """Extract the exam model from the HTML page"""
    # Look for the model-badge class which contains the model name
    model_pattern = re.search(
        r'<span class="model-badge">([^<]+)</span>', html_content)
    if model_pattern:
        return model_pattern.group(1).strip()

    # If we can't find the model with the above pattern, try a more generic approach
    model_pattern = re.search(
        r'[Mm]odel\s*(?:name|type|)?\s*[: ]?\s*([A-Za-z0-9 ]+)', html_content)
    if model_pattern:
        return model_pattern.group(1).strip()

    return "Unknown Model"


def simulate_student(student_index, base_url, auto_saves=3, verbose=False):
    """Simulate a single student's exam flow"""
    session = requests.Session()  # Use session to maintain cookies
    student_data = generate_student_data(student_index)
    start_time = time.time()

    # Generate a unique IP for this student if IP rotation is enabled
    if USE_IP_ROTATION:
        student_ip = generate_random_ip()
        session.headers.update({FAKE_IP_HEADER: student_ip})
        if verbose:
            print(
                f"{BLUE}Student {student_data['student_number']} using IP: {student_ip}{ENDC}")

    try:
        if verbose:
            print(
                f"{BLUE}Student {student_data['student_number']} starting exam process{ENDC}")

        # Step 1: Login
        login_start = time.time()
        login_response = session.post(
            f"{base_url}/student_login",
            data=student_data,
            timeout=30
        )
        login_time = time.time() - login_start
        stats["login_times"].append(login_time)

        if login_response.status_code != 200 or "login" in login_response.url:
            print(
                f"{RED}Login failed for student {student_data['student_number']}{ENDC}")
            stats["failed_requests"] += 1
            return False

        # Step 2: Access the exam page
        exam_start = time.time()
        exam_response = session.get(f"{base_url}/take_exam", timeout=30)
        exam_time = time.time() - exam_start
        stats["exam_load_times"].append(exam_time)

        if exam_response.status_code != 200:
            print(
                f"{RED}Failed to access exam for {student_data['student_number']}{ENDC}")
            stats["failed_requests"] += 1
            return False

        # Extract question IDs from the exam page
        question_ids = extract_questions_from_html(exam_response.text)
        # Get the actual number of questions from the extracted IDs
        num_questions = len(question_ids)

        if num_questions == 0:
            print(
                f"{YELLOW}Warning: Could not extract question IDs for {student_data['student_number']}. HTML parsing may need adjustment.{ENDC}")
            # Try to count question panels as a fallback
            question_panels = re.findall(
                r'class="question-panel"', exam_response.text)
            num_questions = len(question_panels) if question_panels else 5
            print(f"{YELLOW}Using fallback question count: {num_questions}{ENDC}")

        # Extract the model assigned to this student
        model_assigned = extract_model_from_html(exam_response.text)

        # Track the model in our statistics
        if model_assigned not in stats["models_assigned"]:
            stats["models_assigned"][model_assigned] = 0
        stats["models_assigned"][model_assigned] += 1

        if verbose:
            print(
                f"{CYAN}Student {student_data['student_number']} assigned model: {model_assigned} with {num_questions} questions{ENDC}")

        # Generate random answers for questions
        answers = {str(q_id): f"Answer from student {student_index} to question {q_id}"
                   for q_id in question_ids} if question_ids else generate_random_answers(num_questions, student_index=student_index)

        # Step 3: Auto-save answers a few times (simulating work in progress)
        for save_num in range(auto_saves):
            # Modify answers slightly for each save to simulate progress
            current_answers = {
                k: f"Answer from student {student_index} to question {k} (revision {save_num+1})"
                for k in answers.keys()}

            auto_save_start = time.time()
            save_response = session.post(
                f"{base_url}/api/auto_save",
                json={"answers": current_answers,
                      "combinedCode": f"Combined answer from student {student_index} (revision {save_num+1})"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            auto_save_time = time.time() - auto_save_start
            stats["auto_save_times"].append(auto_save_time)

            if save_response.status_code != 200:
                print(
                    f"{RED}Auto-save failed for student {student_data['student_number']}{ENDC}")
                stats["failed_requests"] += 1
                # Continue anyway as this might be just one failed auto-save

            # Add a small delay between auto-saves (100-300ms)
            time.sleep(random.uniform(0.1, 0.3))

        # Step 4: Submit final answers
        final_answers = {
            k: f"Answer from student {student_index} to question {k} (revision {auto_saves+1})"
            for k in answers.keys()}

        submit_start = time.time()
        submit_response = session.post(
            f"{base_url}/api/submit",
            json={"answers": final_answers,
                  "combinedCode": f"Combined answer from student {student_index} (revision {auto_saves+1})"},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        submit_time = time.time() - submit_start
        stats["submission_times"].append(submit_time)

        if submit_response.status_code != 200:
            print(
                f"{RED}Final submission failed for student {student_data['student_number']}{ENDC}")
            stats["failed_requests"] += 1
            return False

        # Calculate total time for this student's exam flow
        total_time = time.time() - start_time
        stats["total_times"].append(total_time)

        if verbose:
            print(
                f"{GREEN}Student {student_data['student_number']} completed exam in {total_time:.2f} seconds{ENDC}")

        stats["successful_students"] += 1
        return True

    except Exception as e:
        print(
            f"{RED}Error for student {student_data['student_number']}: {str(e)}{ENDC}")
        stats["failed_requests"] += 1
        return False


def run_stress_test(base_url, num_students, max_workers, auto_saves, verbose=False):
    """Run the stress test with concurrent students"""
    print(f"{BLUE}Starting stress test with {num_students} students{ENDC}")
    print(f"{BLUE}Using max {max_workers} concurrent connections{ENDC}")
    print(f"{BLUE}Each student will perform {auto_saves} auto-saves plus final submission{ENDC}")

    start_time = time.time()

    # Create a thread pool to simulate concurrent students
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all student simulation tasks
        future_to_student = {
            executor.submit(
                simulate_student,
                i,
                base_url,
                auto_saves,
                verbose
            ): i for i in range(num_students)
        }

        # Process results as they complete
        completed = 0
        for future in concurrent.futures.as_completed(future_to_student):
            student_idx = future_to_student[future]
            try:
                success = future.result()
                completed += 1
                # Print progress every 10% or for verbose mode
                if verbose or completed % max(1, num_students // 10) == 0:
                    progress = (completed / num_students) * 100
                    print(
                        f"{YELLOW}Progress: {completed}/{num_students} students completed ({progress:.1f}%){ENDC}")
            except Exception as e:
                print(
                    f"{RED}Student {student_idx} generated an exception: {str(e)}{ENDC}")

    total_time = time.time() - start_time

    # Calculate and print statistics
    print(f"\n{PURPLE}=== Stress Test Results ==={ENDC}")
    print(f"{GREEN}Total time: {total_time:.2f} seconds{ENDC}")
    print(
        f"{GREEN}Students: {stats['successful_students']}/{num_students} completed successfully{ENDC}")
    print(f"{RED}Failed requests: {stats['failed_requests']}{ENDC}")

    # Only calculate stats if we have successful operations
    if stats["login_times"]:
        print(f"\n{PURPLE}=== Performance Statistics (seconds) ==={ENDC}")
        print(f"Login: avg={statistics.mean(stats['login_times']):.3f}, "
              f"min={min(stats['login_times']):.3f}, "
              f"max={max(stats['login_times']):.3f}")

    if stats["exam_load_times"]:
        print(f"Exam load: avg={statistics.mean(stats['exam_load_times']):.3f}, "
              f"min={min(stats['exam_load_times']):.3f}, "
              f"max={max(stats['exam_load_times']):.3f}")

    if stats["auto_save_times"]:
        print(f"Auto-save: avg={statistics.mean(stats['auto_save_times']):.3f}, "
              # Fixed extra colon in format specifier
              f"min={min(stats['auto_save_times']):.3f}, "
              f"max={max(stats['auto_save_times']):.3f}")

    if stats["submission_times"]:
        print(f"Final submission: avg={statistics.mean(stats['submission_times']):.3f}, "
              f"min={min(stats['submission_times']):.3f}, "
              f"max={max(stats['submission_times']):.3f}")

    if stats["total_times"]:
        print(f"Total student flow: avg={statistics.mean(stats['total_times']):.3f}, "
              f"min={min(stats['total_times']):.3f}, "
              f"max={max(stats['total_times']):.3f}")

    # Display model distribution
    if stats["models_assigned"]:
        print(f"\n{PURPLE}=== Model Distribution ==={ENDC}")
        total_models = sum(stats["models_assigned"].values())
        for model, count in sorted(stats["models_assigned"].items()):
            percentage = (count / total_models) * 100
            print(f"{model}: {count} students ({percentage:.1f}%)")

    print(f"\n{CYAN}Requests per second: {(num_students * (auto_saves + 3)) / total_time:.2f}{ENDC}")
    print(f"{CYAN}(Each student performs 1 login + 1 exam load + {auto_saves} auto-saves + 1 submission = {auto_saves + 3} requests){ENDC}")

    # Create a timestamp for the report
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Save detailed results to a JSON file
    results = {
        "timestamp": timestamp,
        "configuration": {
            "num_students": num_students,
            "concurrent_students": max_workers,
            "auto_saves_per_student": auto_saves,
            "base_url": base_url
        },
        "summary": {
            "total_time_seconds": total_time,
            "successful_students": stats["successful_students"],
            "failed_requests": stats["failed_requests"],
            "requests_per_second": (num_students * (auto_saves + 3)) / total_time
        },
        "detailed_stats": {
            "login_times": stats["login_times"],
            "exam_load_times": stats["exam_load_times"],
            "auto_save_times": stats["auto_save_times"],
            "submission_times": stats["submission_times"],
            "total_times": stats["total_times"],
            "models_assigned": stats["models_assigned"]
        }
    }

    # Write results to file
    results_file = f"stress_test_results_{timestamp}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{GREEN}Detailed results saved to {results_file}{ENDC}")
    return stats["successful_students"] == num_students


def check_active_exam(base_url):
    """Check if there is an active exam in the system"""
    try:
        response = requests.get(f"{base_url}/student_login")
        if response.status_code != 200:
            print(f"{RED}Could not connect to the exam system at {base_url}{ENDC}")
            return False

        # Check if the page indicates no active exam
        if "No active exam available" in response.text:
            print(
                f"{RED}No active exam found in the system. Please activate an exam before running the stress test.{ENDC}")
            return False

        return True
    except requests.RequestException as e:
        print(f"{RED}Error connecting to the exam system: {str(e)}{ENDC}")
        return False


def main():
    """Main function to run the stress test"""
    parser = argparse.ArgumentParser(
        description='Stress Test for Helwan Exam System')
    parser.add_argument('-u', '--url', default=DEFAULT_URL,
                        help=f'Base URL of the exam system (default: {DEFAULT_URL})')
    parser.add_argument('-n', '--num-students', type=int, default=DEFAULT_NUM_STUDENTS,
                        help=f'Number of students to simulate (default: {DEFAULT_NUM_STUDENTS})')
    parser.add_argument('-c', '--concurrent', type=int, default=DEFAULT_CONCURRENT_STUDENTS,
                        help=f'Maximum number of concurrent students (default: {DEFAULT_CONCURRENT_STUDENTS})')
    parser.add_argument('-a', '--auto-saves', type=int, default=DEFAULT_AUTO_SAVES_PER_STUDENT,
                        help=f'Number of auto-saves per student (default: {DEFAULT_AUTO_SAVES_PER_STUDENT})')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed progress for each student')
    parser.add_argument('--skip-check', action='store_true',
                        help='Skip checking for active exam')

    args = parser.parse_args()

    print(f"{BLUE}Helwan Exam System - Stress Test Utility{ENDC}")
    print(f"{BLUE}------------------------------------{ENDC}\n")

    # Check if there is an active exam in the system
    if not args.skip_check and not check_active_exam(args.url):
        print(f"{YELLOW}Hint: To bypass this check, use the --skip-check flag{ENDC}")
        return 1

    try:
        success = run_stress_test(
            args.url,
            args.num_students,
            args.concurrent,
            args.auto_saves,
            args.verbose
        )
        return 0 if success else 1
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stress test interrupted by user{ENDC}")
        return 1
    except Exception as e:
        print(f"\n{RED}Error running stress test: {str(e)}{ENDC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
