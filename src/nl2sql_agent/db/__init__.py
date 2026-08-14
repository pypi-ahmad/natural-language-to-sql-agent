"""Database backends, shared contracts, schema, and seed helpers."""

from .base import DatabaseBackend, DatabaseError, QueryMetrics, QueryPlan, QueryPlanNode
from .database import Database, QueryResult, render_table, setup_db
from .postgres import PostgresDatabase
from .seed import SEED_DEPARTMENTS, SEED_EMPLOYEES

__all__ = [
    "SEED_DEPARTMENTS",
    "SEED_EMPLOYEES",
    "Database",
    "DatabaseBackend",
    "DatabaseError",
    "PostgresDatabase",
    "QueryMetrics",
    "QueryPlan",
    "QueryPlanNode",
    "QueryResult",
    "render_table",
    "setup_db",
]
