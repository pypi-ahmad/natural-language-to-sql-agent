"""Database layer: SQLite wrapper, schema, seed data, and helpers."""

from .database import Database, QueryResult, render_table, setup_db
from .seed import SEED_DEPARTMENTS, SEED_EMPLOYEES

__all__ = [
    "SEED_DEPARTMENTS",
    "SEED_EMPLOYEES",
    "Database",
    "QueryResult",
    "render_table",
    "setup_db",
]
