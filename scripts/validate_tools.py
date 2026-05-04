"""Validate MCP tool schemas for required auth and deterministic structure."""
import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from mcp_project import server


async def main() -> None:
    tools = await server.list_tools()
    for tool in tools:
        schema = tool.inputSchema or {}
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if "auth" not in props:
            raise SystemExit(f"Tool {tool.name} is missing auth schema")
        if "auth" not in required:
            raise SystemExit(f"Tool {tool.name} does not require auth")
    print("Tool schemas validated.")


if __name__ == "__main__":
    asyncio.run(main())
