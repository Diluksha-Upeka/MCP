"""
server.py — MCP stdio/sse server for the Enterprise Data Agent.

Exposes enterprise database tools via the Model Context Protocol.
Run with:  python mcp_project/server.py --transport <stdio|sse>
"""
import asyncio
import json
import argparse
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
import uvicorn
from mcp.types import (
    Tool, TextContent, CallToolResult,
    Resource, Prompt, PromptMessage, GetPromptResult
)

from db import add_user, deactivate_user, get_active_users, get_user_stats, search_users

app = Server("sqlite-mcp-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List of all available tools."""
    return [
        Tool(
            name="get_active_users",
            description="Fetches all active users and their roles from the enterprise database.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="add_user",
            description="Adds a new active user to the enterprise database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The full name of the user to add."},
                    "role": {"type": "string", "description": "Job role: Employee, Manager, Admin, Engineer, Intern, or Director. Defaults to Employee."}
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
                    "name": {"type": "string", "description": "The full name of the user to deactivate."}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_user_stats",
            description="Returns a summary of total, active, and inactive user counts.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="search_users",
            description="Searches users by a name fragment. Returns name, role, and status for all matches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A name fragment to search for."}
                },
                "required": ["query"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle tool execution requests."""
    if name == "get_active_users":
        data = get_active_users()
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, indent=2))])

    elif name == "add_user":
        result = add_user(name=arguments.get("name", ""), role=arguments.get("role", "Employee"))
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    elif name == "deactivate_user":
        result = deactivate_user(name=arguments.get("name", ""))
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    elif name == "get_user_stats":
        result = get_user_stats()
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "search_users":
        result = search_users(query=arguments.get("query", ""))
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    raise ValueError(f"Unknown tool: '{name}'")


@app.list_resources()
async def list_resources() -> list[Resource]:
    """Expose available resources."""
    return [
        Resource(
            uri="file:///schema.sql",
            name="Database Schema",
            description="The SQLite database schema containing the users table structure.",
            mimeType="text/plain"
        )
    ]


@app.read_resource()
async def read_resource(uri: str) -> str | bytes:
    """Read a requested resource."""
    if uri == "file:///schema.sql":
        schema_path = Path(__file__).parent.parent / "schema.sql"
        if schema_path.exists():
            return schema_path.read_text(encoding="utf-8")
        return "Error: Schema file not found."
    raise ValueError(f"Unknown resource: {uri}")


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """Expose available system prompts."""
    return [
        Prompt(
            name="hr-assistant",
            description="A system prompt configuring the AI to act as a helpful enterprise HR assistant.",
            arguments=[]
        )
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
    """Return a requested system prompt."""
    if name == "hr-assistant":
        return GetPromptResult(
            description="Professional HR Assistant role context.",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="You are a helpful Enterprise HR Assistant. You have access to the SQLite database representing our active employee roster. Keep answers professional, concise, and focused on managing user status and roles."
                    )
                )
            ]
        )
    raise ValueError(f"Unknown prompt: {name}")


async def main():
    parser = argparse.ArgumentParser(description="Run the MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport protocol to use (stdio or sse)")
    parser.add_argument("--port", type=int, default=8000, help="Port to run SSE server on")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"Starting SSE MCP Server on port {args.port}...")
        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await app.run(streams[0], streams[1], app.create_initialization_options())

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        starlette_app = Starlette(routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Route("/messages", endpoint=handle_messages, methods=["POST"])
        ])

        uvicorn.run(starlette_app, host="0.0.0.0", port=args.port)
    else:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
