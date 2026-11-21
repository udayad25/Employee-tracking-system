"""Oracle database helpers used by the EMTS application.

The project intentionally uses parameterized SQL with python-oracledb instead
of Django ORM models. This keeps the database schema easy to inspect in SQL
Developer and makes every query explicit for learning purposes.
"""

from __future__ import annotations

import os
from typing import Any

import oracledb
from dotenv import load_dotenv

load_dotenv()

_connection_pool: oracledb.ConnectionPool | None = None


def get_pool() -> oracledb.ConnectionPool:
    """Create the Oracle connection pool once and reuse it across requests."""
    global _connection_pool

    if _connection_pool is None:
        username = os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD")
        dsn = os.getenv("ORACLE_DSN")

        if not all((username, password, dsn)):
            raise RuntimeError(
                "Oracle settings are missing. Add ORACLE_USER, "
                "ORACLE_PASSWORD and ORACLE_DSN to your .env file."
            )

        _connection_pool = oracledb.create_pool(
            user=username,
            password=password,
            dsn=dsn,
            min=1,
            max=5,
            increment=1,
        )

    return _connection_pool


def query(
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    one: bool = False,
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """Run a SELECT statement and return rows as dictionaries.

    Bind variables are used for values. Never build SQL by joining user input
    into the query string.
    """
    with get_pool().acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or {})

            if cursor.description is None:
                return None

            column_names = [column[0].lower() for column in cursor.description]
            results = []

            for row in cursor.fetchall():
                record = {}
                for column_name, value in zip(column_names, row):
                    if isinstance(value, oracledb.LOB):
                        value = value.read()
                    record[column_name] = value
                results.append(record)

            if one:
                return results[0] if results else None

            return results


def execute(sql: str, params: dict[str, Any] | None = None) -> int:
    """Run an INSERT, UPDATE or DELETE statement and commit the transaction."""
    with get_pool().acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or {})
            affected_rows = cursor.rowcount
            connection.commit()
            return affected_rows
