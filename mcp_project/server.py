"""
server.py — MCP stdio server for the Enterprise Data Agent.

Exposes enterprise database tools via the Model Context Protocol.
Run with:  python mcp_project/server.py
"""
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

from db import add_user, deactivate_user, get_active_users, get_user_stats, search_users

app = Server("sqlite-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_active_users",
            description="Fetches all active users and their roles from the enterprise database.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="add_user",
            description="Adds a new active user to the enterprise database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the user to add."
                    },
                    "role": {
                        "type": "string",
                        "description": "Job role: Employee, Manager, Admin, Engineer, Intern, or Director. Defaults to Employee."
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="deactivate_user",
            description="Deactivates an active user by their full name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full name of the user to deactivate."
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_user_stats",
            description="Returns a summary of total, active, and inactive user counts.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="search_users",
            description="Searches users by a name fragment. Returns name, role, and status for all matches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A name fragment to search for (case-insensitive)."
                    }
                },
                "required": ["query"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    if name == "get_active_users":
        data = get_active_users()
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(data, indent=2))]
        )

    elif name == "add_user":
        result = add_user(
            name=arguments.get("name", ""),
            role=arguments.get("role", "Employee")
        )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result))]
        )

    elif name == "deactivate_user":
        result = deactivate_user(name=arguments.get("name", ""))
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result))]
        )

    elif name == "get_user_stats":
        result = get_user_stats()
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, indent=2))]
        )

    elif name == "search_users":
        result = search_users(query=arguments.get("query", ""))
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, indent=2))]
        )

    raise ValueError(f"Unknown tool: '{name}'")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())