"""
Tests for backend.setup_db() — database initialization.
Target: backend.py lines 18-40.

Coverage intent:
- Table creation (departments, employees)
- Schema correctness (column names, types)
- Data integrity (exact seed values)
- Idempotency (double-call does not duplicate)
- File creation side effect
"""
import sqlite3
import os
import pytest


class TestSetupDbTableCreation:
    """Verify setup_db() creates the expected tables."""

    def test_creates_departments_table(self, tmp_db_dir):
        """backend.py:31 — CREATE TABLE IF NOT EXISTS departments."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='departments'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_employees_table(self, tmp_db_dir):
        """backend.py:35 — CREATE TABLE IF NOT EXISTS employees."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_company_db_file(self, tmp_db_dir):
        """setup_db() must create 'company.db' in the working directory."""
        assert not os.path.exists("company.db")
        from backend import setup_db
        setup_db()
        assert os.path.exists("company.db")


class TestSetupDbSchema:
    """Verify the column definitions match backend.py source."""

    def test_departments_columns(self, tmp_db_dir):
        """backend.py:31 — dept_id INTEGER PK, dept_name TEXT, location TEXT."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(departments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        assert columns == {
            "dept_id": "INTEGER",
            "dept_name": "TEXT",
            "location": "TEXT",
        }

    def test_employees_columns(self, tmp_db_dir):
        """backend.py:35 — emp_id INTEGER PK, name TEXT, salary REAL, dept_id INTEGER."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(employees)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        assert columns == {
            "emp_id": "INTEGER",
            "name": "TEXT",
            "salary": "REAL",
            "dept_id": "INTEGER",
        }


class TestSetupDbSeedData:
    """Verify inserted rows match backend.py lines 32-38."""

    def test_inserts_three_departments(self, tmp_db_dir):
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM departments")
        assert cursor.fetchone()[0] == 3
        conn.close()

    def test_inserts_five_employees(self, tmp_db_dir):
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        assert cursor.fetchone()[0] == 5
        conn.close()

    def test_department_exact_values(self, tmp_db_dir):
        """Verify exact rows from backend.py:32-34."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM departments ORDER BY dept_id")
        rows = cursor.fetchall()
        conn.close()
        assert rows == [
            (101, "Engineering", "New York"),
            (102, "Sales", "San Francisco"),
            (103, "HR", "Remote"),
        ]

    def test_employee_exact_values(self, tmp_db_dir):
        """Verify exact rows from backend.py:36-38."""
        from backend import setup_db
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM employees ORDER BY emp_id")
        rows = cursor.fetchall()
        conn.close()
        assert rows == [
            (1, "Alice", 120000.0, 101),
            (2, "Bob", 85000.0, 102),
            (3, "Charlie", 115000.0, 101),
            (4, "Diana", 95000.0, 103),
            (5, "Eve", 88000.0, 102),
        ]


class TestSetupDbIdempotency:
    """Verify INSERT OR IGNORE prevents duplication."""

    def test_double_call_no_duplicate_departments(self, tmp_db_dir):
        """Calling setup_db() twice must NOT double the rows."""
        from backend import setup_db
        setup_db()
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM departments")
        assert cursor.fetchone()[0] == 3
        conn.close()

    def test_double_call_no_duplicate_employees(self, tmp_db_dir):
        from backend import setup_db
        setup_db()
        setup_db()
        conn = sqlite3.connect("company.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM employees")
        assert cursor.fetchone()[0] == 5
        conn.close()
