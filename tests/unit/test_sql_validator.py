"""Tests for the SQL safety validator."""

from __future__ import annotations

import pytest

from nl2sql_agent.security import (
    DANGEROUS_FUNCTIONS,
    SQLPolicy,
    SQLValidationError,
    parse_sql,
    referenced_tables,
    validate_sql,
)


class TestSafeQueries:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT 1",
            "SELECT * FROM employees",
            "SELECT name, salary FROM employees WHERE salary > 100000",
            "SELECT d.dept_name, COUNT(*) FROM departments d JOIN employees e "
            "ON d.dept_id = e.dept_id GROUP BY d.dept_name",
            "SELECT * FROM employees ORDER BY salary DESC LIMIT 5",
            "SELECT name FROM employees WHERE name LIKE 'A%'",
            "WITH dept_total AS (SELECT dept_id, SUM(salary) AS total FROM employees "
            "GROUP BY dept_id) SELECT * FROM dept_total",
            "SELECT * FROM employees UNION SELECT * FROM departments",
        ],
    )
    def test_valid(self, sql):
        # Should not raise.
        validate_sql(sql)


class TestDestructiveStatements:
    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE employees",
            "DELETE FROM employees",
            "INSERT INTO employees VALUES (1, 'X', 0, 1)",
            "UPDATE employees SET salary = 0",
            "TRUNCATE employees",
            "ALTER TABLE employees ADD COLUMN x TEXT",
            "CREATE TABLE foo (x INT)",
            "REPLACE INTO employees VALUES (1, 'X', 0, 1)",
            "ATTACH DATABASE 'evil.db' AS evil",
            "DETACH DATABASE evil",
            "VACUUM",
            "REINDEX",
            "PRAGMA writable_schema = 1",
            "GRANT ALL ON employees TO public",
        ],
    )
    def test_blocked(self, sql):
        with pytest.raises(SQLValidationError):
            validate_sql(sql)


class TestMultiStatement:
    def test_two_selects(self):
        with pytest.raises(SQLValidationError, match="Multiple"):
            validate_sql("SELECT 1; SELECT 2")

    def test_select_then_drop(self):
        with pytest.raises(SQLValidationError, match="Multiple"):
            validate_sql("SELECT 1; DROP TABLE x")


class TestDangerousFunctions:
    @pytest.mark.parametrize("fn", sorted(DANGEROUS_FUNCTIONS))
    def test_blocked(self, fn):
        with pytest.raises(SQLValidationError):
            validate_sql(f"SELECT {fn}('evil')")

    def test_safe_aggregate_allowed_by_default(self):
        validate_sql("SELECT COUNT(*) FROM employees")
        validate_sql("SELECT SUM(salary) FROM employees")
        validate_sql("SELECT AVG(salary), MAX(salary), MIN(salary) FROM employees")

    def test_aggregate_blocked_when_disabled(self):
        with pytest.raises(SQLValidationError, match="[Aa]ggregate"):
            validate_sql(
                "SELECT COUNT(*) FROM employees",
                policy=SQLPolicy(allow_aggregates=False),
            )


class TestSubqueries:
    def test_nested_select_blocked_when_disallowed(self):
        with pytest.raises(SQLValidationError, match="[Ss]ubquer"):
            validate_sql(
                "SELECT * FROM employees WHERE dept_id IN (SELECT dept_id FROM departments)",
                policy=SQLPolicy(allow_subqueries=False),
            )

    def test_subquery_allowed_by_default(self):
        validate_sql(
            "SELECT * FROM employees WHERE dept_id IN (SELECT dept_id FROM departments)",
        )


class TestJoins:
    def test_join_blocked_when_disallowed(self):
        with pytest.raises(SQLValidationError, match="JOIN"):
            validate_sql(
                "SELECT a.*, b.* FROM employees a JOIN departments b ON a.dept_id = b.dept_id",
                policy=SQLPolicy(allow_joins=False),
            )

    def test_join_allowed_by_default(self):
        validate_sql(
            "SELECT a.*, b.* FROM employees a JOIN departments b ON a.dept_id = b.dept_id",
        )


class TestCTE:
    def test_cte_blocked_when_disallowed(self):
        with pytest.raises(SQLValidationError, match="CTE"):
            validate_sql(
                "WITH x AS (SELECT 1) SELECT * FROM x",
                policy=SQLPolicy(allow_cte=False),
            )

    def test_cte_allowed_by_default(self):
        validate_sql("WITH x AS (SELECT 1) SELECT * FROM x")


class TestUnion:
    def test_union_blocked_when_disallowed(self):
        with pytest.raises(SQLValidationError, match="[Ss]et"):
            validate_sql(
                "SELECT 1 UNION SELECT 2",
                policy=SQLPolicy(allow_union=False),
            )

    def test_union_allowed_by_default(self):
        validate_sql("SELECT 1 UNION SELECT 2")


class TestFalsePositives:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM updated_at",
            "SELECT dropoff_date FROM trips",
            "SELECT * FROM deleted_records",
            "SELECT inserted_at, updated_at FROM events",
        ],
    )
    def test_column_names_not_blocked(self, sql):
        # Should not raise: these are column names, not destructive statements.
        validate_sql(sql)


class TestEmptyAndInvalid:
    def test_empty_string(self):
        with pytest.raises(SQLValidationError, match="[Ee]mpty"):
            validate_sql("")

    def test_whitespace_only(self):
        with pytest.raises(SQLValidationError):
            validate_sql("   \n\t  ")

    def test_garbage(self):
        with pytest.raises(SQLValidationError):
            validate_sql("not even sql at all")


class TestReferencedTables:
    def test_simple(self):
        assert referenced_tables("SELECT * FROM employees") == {"employees"}

    def test_join(self):
        assert referenced_tables(
            "SELECT a.name FROM employees a JOIN departments b ON a.dept_id = b.dept_id",
        ) == {"employees", "departments"}

    def test_subquery(self):
        assert referenced_tables(
            "SELECT * FROM employees WHERE dept_id IN (SELECT dept_id FROM departments)",
        ) == {"employees", "departments"}

    def test_invalid_sql_raises(self):
        # Truly malformed SQL raises SQLValidationError.
        with pytest.raises(SQLValidationError):
            referenced_tables("not sql at all")


class TestParseSql:
    def test_returns_selects(self):
        stmts = parse_sql("SELECT 1")
        assert len(stmts) == 1
        assert stmts[0].sql().upper().startswith("SELECT")

    def test_empty(self):
        with pytest.raises(SQLValidationError):
            parse_sql("")
