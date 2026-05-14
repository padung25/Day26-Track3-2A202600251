from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

try:
    from .db import SQLiteAdapter, ValidationError, default_db_path
    from .init_db import create_database
except ImportError:  # pragma: no cover - direct script execution
    from db import SQLiteAdapter, ValidationError, default_db_path
    from init_db import create_database


DB_PATH = Path(os.environ.get("SQLITE_LAB_DB_PATH", default_db_path()))
create_database(DB_PATH)
adapter = SQLiteAdapter(DB_PATH)
mcp = FastMCP("SQLite Lab MCP Server")


def safe_call(action, error_cls=ToolError):
    try:
        return action()
    except ValidationError as exc:
        raise error_cls(str(exc)) from exc


@mcp.tool(name="search")
def search(
    table: str,
    filters: list[dict[str, Any]] | dict[str, Any] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows with validated filters, ordering, and pagination."""
    return safe_call(
        lambda: adapter.search(
            table=table,
            filters=filters,
            columns=columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    )


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert one row into a validated table and return the inserted payload."""
    return safe_call(lambda: adapter.insert(table=table, values=values))


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict[str, Any]] | dict[str, Any] | None = None,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Run a validated aggregate query such as count, avg, sum, min, or max."""
    return safe_call(
        lambda: adapter.aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    )


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full SQLite database schema as JSON text."""
    return safe_call(lambda: adapter.schema_json(), ResourceError)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return one table schema as JSON text."""
    return safe_call(lambda: adapter.schema_json(table_name), ResourceError)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SQLite lab FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use. The lab and Codex client workflow use stdio.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
