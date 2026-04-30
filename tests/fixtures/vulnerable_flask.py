"""Vulnerable Flask Application - For Security Review Testing.

Contains intentional vulnerabilities across all categories:
- SQL Injection (CWE-89)
- XSS (CWE-79)
- Command Injection (CWE-78)
- Path Traversal (CWE-22)
- Hardcoded Credentials (CWE-798)
- Insecure Deserialization (CWE-502)
- IDOR (CWE-639)
- N+1 Query (Performance)
- Race Condition (Logic)
- Missing Error Handling (Standards)
"""

import os
import sqlite3
import pickle
import subprocess
from flask import Flask, request, render_template_string, jsonify, send_file

app = Flask(__name__)

# VULNERABILITY: Hardcoded credentials (CWE-798)
DATABASE_URL = "postgresql://admin:SuperSecret123@localhost:5432/myapp"
SECRET_KEY = "my-static-secret-key-do-not-use-in-production"
API_TOKEN = "sk-8a9f7e6d5c4b3a2e1d0c9b8a7f6e5d4c"

# VULNERABILITY: N+1 query pattern
def get_users_with_orders():
    """Fetches users then queries orders one by one - O(n) DB calls."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    users = cursor.execute("SELECT id, name FROM users").fetchall()
    result = []
    for user in users:
        # N+1: Each user triggers a separate query
        orders = cursor.execute(
            f"SELECT * FROM orders WHERE user_id = {user[0]}"
        ).fetchall()
        result.append({"user": user, "orders": orders})

    conn.close()
    return result


# VULNERABILITY: Raw f-string in SQL (CWE-89)
def get_user_by_name(username: str):
    """SQL injection via f-string in query."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
    result = cursor.fetchall()
    conn.close()
    return result


# VULNERABILITY: SQL injection with dynamic ORDER BY (CWE-89)
def get_products_sorted(sort_by: str, direction: str):
    """SQL injection via ORDER BY clause."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM products ORDER BY {sort_by} {direction}")
    result = cursor.fetchall()
    conn.close()
    return result


# VULNERABILITY: Command injection (CWE-78)
def ping_host(host: str) -> str:
    """Command injection via user input in shell command."""
    result = subprocess.check_output(f"ping -c 1 {host}", shell=True)
    return result.decode()


# VULNERABILITY: Path traversal (CWE-22)
def read_file(filename: str):
    """Path traversal via unsanitized file path."""
    filepath = os.path.join("/var/app/files", filename)
    with open(filepath, "r") as f:
        return f.read()


# VULNERABILITY: Insecure deserialization (CWE-502)
def load_session(session_data: bytes):
    """Insecure deserialization of untrusted pickle data."""
    return pickle.loads(session_data)


# VULNERABILITY: XSS via render_template_string with user input (CWE-79)
def render_user_comment(username: str, comment: str):
    """Reflected XSS via template injection."""
    template = f"<h1>Welcome {username}</h1><p>{comment}</p>"
    return render_template_string(template)


# VULNERABILITY: XSS via unescaped JSON response
def search_users(query: str):
    """Returns unsanitized user input in JSON."""
    return f"<div>Search results for: {query}</div>"


# VULNERABILITY: IDOR - no authorization check (CWE-639)
def get_user_profile(user_id: int):
    """Direct object reference without ownership verification."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", [user_id])
    return cursor.fetchone()


# VULNERABILITY: Race condition
user_balance_cache = {}


def transfer_funds(from_user: int, to_user: int, amount: float):
    """Race condition: Read-modify-write without locking."""
    if from_user not in user_balance_cache:
        user_balance_cache[from_user] = 1000.0
    if to_user not in user_balance_cache:
        user_balance_cache[to_user] = 500.0

    if user_balance_cache[from_user] >= amount:
        user_balance_cache[from_user] -= amount
        user_balance_cache[to_user] += amount
        return True
    return False


# VULNERABILITY: Bare except, swallowed exception
def parse_json_data(raw_data: str):
    """Swallowed exception with broad except clause."""
    try:
        import json
        return json.loads(raw_data)
    except:
        return None


# VULNERABILITY: Information leak in error messages
def login(username: str, password: str) -> dict:
    """Different error messages reveal valid usernames."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    user = cursor.execute(
        "SELECT * FROM users WHERE name = ?", [username]
    ).fetchone()

    if not user:
        return {"error": "User not found"}  # Reveals username doesn't exist

    if user[2] != password:  # Plaintext password comparison
        return {"error": "Invalid password"}  # Reveals username exists

    return {"success": True, "token": SECRET_KEY}


# VULNERABILITY: Open redirect (CWE-601)
def redirect_after_login(target_url: str):
    """Unvalidated redirect URL."""
    from flask import redirect
    return redirect(target_url)


# VULNERABILITY: Unbounded memory growth
uploaded_files_cache = {}


def cache_file_upload(file_id: str, content: bytes):
    """Unbounded cache can cause memory exhaustion."""
    global uploaded_files_cache
    uploaded_files_cache[file_id] = content


# VULNERABILITY: Missing rate limiting / resource exhaustion
def fibonacci(n: int) -> int:
    """Exponential complexity without input validation."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


# Routes (simplified - would normally use @app.route)
def setup_routes():
    pass


if __name__ == "__main__":
    app.run(debug=True)  # Debug mode in production
