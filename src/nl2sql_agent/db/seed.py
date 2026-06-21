"""Seed data for the demo company database."""

from __future__ import annotations

# Each tuple is (id, name, location) for the departments table.
SEED_DEPARTMENTS: tuple[tuple[int, str, str], ...] = (
    (101, "Engineering", "New York"),
    (102, "Sales", "San Francisco"),
    (103, "HR", "Remote"),
    (104, "Marketing", "London"),
)

# Each tuple is (id, name, salary, dept_id) for the employees table.
SEED_EMPLOYEES: tuple[tuple[int, str, float, int], ...] = (
    (1, "Alice", 120_000, 101),
    (2, "Bob", 85_000, 102),
    (3, "Charlie", 115_000, 101),
    (4, "Diana", 95_000, 103),
    (5, "Eve", 88_000, 102),
    (6, "Frank", 142_500, 101),
    (7, "Grace", 78_000, 103),
    (8, "Hank", 105_000, 102),
    (9, "Ivy", 132_000, 104),
    (10, "Jack", 91_000, 104),
)
