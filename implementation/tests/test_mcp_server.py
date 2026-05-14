from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client

from implementation.mcp_server import mcp


def payload(result):
    if hasattr(result, "data"):
        return result.data
    return result


def test_mcp_tools_resources_and_calls():
    asyncio.run(run_mcp_checks())


async def run_mcp_checks():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {"search", "insert", "aggregate"}

        resources = await client.list_resources()
        assert "schema://database" in {str(resource.uri) for resource in resources}

        templates = await client.list_resource_templates()
        assert "schema://table/{table_name}" in {str(template.uriTemplate) for template in templates}

        schema = await client.read_resource("schema://table/students")
        assert json.loads(schema[0].text)["table"] == "students"

        search_result = payload(
            await client.call_tool(
                "search",
                {
                    "table": "students",
                    "filters": {"column": "cohort", "op": "eq", "value": "A1"},
                    "limit": 2,
                },
            )
        )
        assert search_result["table"] == "students"
        assert search_result["count"] == 2

        aggregate_result = payload(
            await client.call_tool(
                "aggregate",
                {"table": "enrollments", "metric": "avg", "column": "score", "group_by": "status"},
            )
        )
        assert aggregate_result["metric"] == "avg"
        assert aggregate_result["rows"]

        with pytest.raises(Exception, match="Unknown table"):
            await client.call_tool("search", {"table": "missing_table"})
