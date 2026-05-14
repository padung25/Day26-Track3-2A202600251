from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when a request cannot be safely executed."""


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILTER_OPERATORS = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
}
AGGREGATE_METRICS = {"count", "avg", "sum", "min", "max"}
NUMERIC_TYPES = {"INTEGER", "REAL", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE"}


def default_db_path() -> Path:
    return Path(__file__).with_name("learning_analytics.sqlite3")


class SQLiteAdapter:
    def __init__(self, db_path: str | Path | None = None, max_limit: int = 100):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.max_limit = max_limit

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def list_tables(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        table = self.validate_table(table)
        with self.connect() as connection:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            foreign_keys = connection.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()

        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in columns
            ],
            "foreign_keys": [
                {
                    "column": row["from"],
                    "references_table": row["table"],
                    "references_column": row["to"],
                }
                for row in foreign_keys
            ],
        }

    def get_database_schema(self) -> dict[str, Any]:
        tables = self.list_tables()
        return {
            "database": str(self.db_path),
            "tables": {table: self.get_table_schema(table) for table in tables},
        }

    def schema_json(self, table: str | None = None) -> str:
        payload = self.get_table_schema(table) if table else self.get_database_schema()
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def search(
        self,
        table: str,
        filters: list[dict[str, Any]] | dict[str, Any] | None = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table = self.validate_table(table)
        table_columns = self.column_names(table)
        selected_columns = self.validate_columns(table, columns) if columns else table_columns
        limit, offset = self.validate_pagination(limit, offset)
        where_sql, params = self.build_where_clause(table, filters)

        sql = f'SELECT {", ".join(self.quote_identifier(column) for column in selected_columns)} FROM {self.quote_identifier(table)}'
        if where_sql:
            sql += f" WHERE {where_sql}"
        if order_by:
            self.validate_column(table, order_by)
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {self.quote_identifier(order_by)} {direction}"
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns,
            "count": len(rows),
            "limit": limit,
            "offset": offset,
            "rows": rows,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table = self.validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("Insert values must be a non-empty object.")

        columns = list(values.keys())
        self.validate_columns(table, columns)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(self.quote_identifier(column) for column in columns)
        sql = f"INSERT INTO {self.quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"

        with self.connect() as connection:
            cursor = connection.execute(sql, [values[column] for column in columns])
            inserted_id = cursor.lastrowid
            connection.commit()
            row = connection.execute(
                f"SELECT * FROM {self.quote_identifier(table)} WHERE rowid = ?",
                [inserted_id],
            ).fetchone()

        return {
            "table": table,
            "inserted_id": inserted_id,
            "row": dict(row) if row else dict(values),
        }

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        table = self.validate_table(table)
        metric = metric.lower()
        if metric not in AGGREGATE_METRICS:
            allowed = ", ".join(sorted(AGGREGATE_METRICS))
            raise ValidationError(f"Unsupported aggregate metric '{metric}'. Allowed metrics: {allowed}.")

        if metric == "count":
            aggregate_target = "*" if column is None else self.quote_identifier(self.validate_column(table, column))
        else:
            if column is None:
                raise ValidationError(f"Aggregate metric '{metric}' requires a column.")
            column = self.validate_column(table, column)
            if not self.is_numeric_column(table, column):
                raise ValidationError(f"Aggregate metric '{metric}' requires a numeric column; '{column}' is not numeric.")
            aggregate_target = self.quote_identifier(column)

        select_parts = []
        if group_by:
            group_by = self.validate_column(table, group_by)
            select_parts.append(f"{self.quote_identifier(group_by)} AS group_key")
        select_parts.append(f"{metric.upper()}({aggregate_target}) AS value")

        where_sql, params = self.build_where_clause(table, filters)
        sql = f"SELECT {', '.join(select_parts)} FROM {self.quote_identifier(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if group_by:
            sql += f" GROUP BY {self.quote_identifier(group_by)} ORDER BY {self.quote_identifier(group_by)}"

        with self.connect() as connection:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_by,
            "rows": rows,
        }

    def validate_table(self, table: str) -> str:
        self.validate_identifier(table, "table")
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(f"Unknown table '{table}'. Available tables: {', '.join(tables)}.")
        return table

    def validate_column(self, table: str, column: str) -> str:
        self.validate_identifier(column, "column")
        available = self.column_names(table)
        if column not in available:
            raise ValidationError(f"Unknown column '{column}' for table '{table}'. Available columns: {', '.join(available)}.")
        return column

    def validate_columns(self, table: str, columns: list[str]) -> list[str]:
        if not isinstance(columns, list) or not columns:
            raise ValidationError("Columns must be a non-empty list when provided.")
        return [self.validate_column(table, column) for column in columns]

    def validate_identifier(self, identifier: str, label: str) -> None:
        if not isinstance(identifier, str) or not IDENTIFIER_RE.match(identifier):
            raise ValidationError(f"Invalid {label} identifier '{identifier}'.")

    def validate_pagination(self, limit: int, offset: int) -> tuple[int, int]:
        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("Limit must be a positive integer.")
        if limit > self.max_limit:
            raise ValidationError(f"Limit must be at most {self.max_limit}.")
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer.")
        return limit, offset

    def column_names(self, table: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [row["name"] for row in rows]

    def column_type(self, table: str, column: str) -> str:
        with self.connect() as connection:
            rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        for row in rows:
            if row["name"] == column:
                return str(row["type"]).upper()
        raise ValidationError(f"Unknown column '{column}' for table '{table}'.")

    def is_numeric_column(self, table: str, column: str) -> bool:
        column_type = self.column_type(table, column)
        return any(type_name in column_type for type_name in NUMERIC_TYPES)

    def build_where_clause(
        self,
        table: str,
        filters: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> tuple[str, list[Any]]:
        if filters is None:
            return "", []
        normalized_filters = [filters] if isinstance(filters, dict) else filters
        if not isinstance(normalized_filters, list):
            raise ValidationError("Filters must be an object or a list of objects.")

        clauses: list[str] = []
        params: list[Any] = []
        for item in normalized_filters:
            if not isinstance(item, dict):
                raise ValidationError("Each filter must be an object.")
            column = self.validate_column(table, item.get("column"))
            op = item.get("op", "eq")
            if op not in FILTER_OPERATORS:
                allowed = ", ".join(FILTER_OPERATORS)
                raise ValidationError(f"Unsupported filter operator '{op}'. Allowed operators: {allowed}.")
            value = item.get("value")
            sql_op = FILTER_OPERATORS[op]
            if op == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("The 'in' operator requires a non-empty list value.")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{self.quote_identifier(column)} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{self.quote_identifier(column)} {sql_op} ?")
                params.append(value)

        return " AND ".join(clauses), params

    def quote_identifier(self, identifier: str) -> str:
        self.validate_identifier(identifier, "SQL")
        return f'"{identifier}"'
