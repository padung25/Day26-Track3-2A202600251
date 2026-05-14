from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from fastmcp import Client

try:
    from .mcp_server import mcp
except ImportError:  # pragma: no cover - direct script execution
    from mcp_server import mcp


def print_json(label: str, payload) -> None:
    print(f"\n## {label}")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def tool_payload(result):
    if hasattr(result, "data"):
        return result.data
    return result


async def main() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        resource_templates = await client.list_resource_templates()

        print_json("Tools", [tool.name for tool in tools])
        print_json("Resources", [str(resource.uri) for resource in resources])
        print_json("Resource templates", [str(template.uriTemplate) for template in resource_templates])

        schema = await client.read_resource("schema://database")
        print_json("schema://database", str(schema[0].text)[:600] + "...")

        search_result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": {"column": "cohort", "op": "eq", "value": "A1"},
                "columns": ["id", "name", "cohort"],
                "limit": 3,
                "order_by": "name",
            },
        )
        print_json("search students cohort A1", tool_payload(search_result))

        aggregate_result = await client.call_tool(
            "aggregate",
            {
                "table": "enrollments",
                "metric": "avg",
                "column": "score",
                "group_by": "status",
            },
        )
        print_json("average score by status", tool_payload(aggregate_result))

        insert_result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Minh Demo",
                    "email": f"minh.demo.{uuid4().hex[:8]}@example.com",
                    "cohort": "A1",
                },
            },
        )
        print_json("insert student", tool_payload(insert_result))

        try:
            logging.disable(logging.CRITICAL)
            await client.call_tool("search", {"table": "missing_table"})
        except Exception as exc:  # noqa: BLE001 - verification should display MCP errors plainly.
            print_json("expected invalid table error", {"error": str(exc)})
        finally:
            logging.disable(logging.NOTSET)


if __name__ == "__main__":
    asyncio.run(main())
