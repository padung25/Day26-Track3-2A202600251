from __future__ import annotations

import json

import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "lab.sqlite3"
    create_database(db_path, reset=True)
    return SQLiteAdapter(db_path)


def test_search_filters_order_and_pagination(adapter):
    result = adapter.search(
        "students",
        filters={"column": "cohort", "op": "eq", "value": "A1"},
        columns=["id", "name", "cohort"],
        limit=2,
        offset=0,
        order_by="name",
    )

    assert result["count"] == 2
    assert result["columns"] == ["id", "name", "cohort"]
    assert [row["cohort"] for row in result["rows"]] == ["A1", "A1"]
    assert result["rows"][0]["name"] == "An Nguyen"


def test_insert_returns_inserted_row(adapter):
    result = adapter.insert(
        "students",
        {"name": "Linh Test", "email": "linh.test@example.com", "cohort": "B1"},
    )

    assert result["inserted_id"] > 0
    assert result["row"]["name"] == "Linh Test"
    assert result["row"]["cohort"] == "B1"


@pytest.mark.parametrize("metric", ["count", "avg", "sum", "min", "max"])
def test_aggregate_metrics(adapter, metric):
    column = None if metric == "count" else "score"
    result = adapter.aggregate("enrollments", metric=metric, column=column)

    assert result["metric"] == metric
    assert len(result["rows"]) == 1
    assert "value" in result["rows"][0]


def test_grouped_aggregate(adapter):
    result = adapter.aggregate("enrollments", metric="avg", column="score", group_by="status")

    groups = {row["group_key"] for row in result["rows"]}
    assert {"active", "completed", "dropped"} <= groups


def test_schema_json(adapter):
    database_schema = json.loads(adapter.schema_json())
    table_schema = json.loads(adapter.schema_json("students"))

    assert "students" in database_schema["tables"]
    assert table_schema["table"] == "students"
    assert any(column["name"] == "email" for column in table_schema["columns"])


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda adapter: adapter.search("missing_table"), "Unknown table"),
        (lambda adapter: adapter.search("students", columns=["missing_column"]), "Unknown column"),
        (
            lambda adapter: adapter.search("students", filters={"column": "cohort", "op": "regex", "value": "A"}),
            "Unsupported filter operator",
        ),
        (lambda adapter: adapter.aggregate("students", metric="median", column="id"), "Unsupported aggregate metric"),
        (lambda adapter: adapter.aggregate("students", metric="avg", column="name"), "requires a numeric column"),
        (lambda adapter: adapter.insert("students", {}), "non-empty object"),
        (lambda adapter: adapter.search("students; DROP TABLE students"), "Invalid table identifier"),
        (lambda adapter: adapter.search("students", limit=-1), "Limit must be a positive integer"),
        (lambda adapter: adapter.search("students", offset=-1), "Offset must be a non-negative integer"),
    ],
)
def test_validation_errors(adapter, call, message):
    with pytest.raises(ValidationError, match=message):
        call(adapter)
