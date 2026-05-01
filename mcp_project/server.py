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
from starlette.responses import JSONResponse
from starlette.requests import Request
import uvicorn
from mcp.types import (
    Tool, TextContent, CallToolResult,
    Resource, Prompt, PromptMessage, GetPromptResult
)

from auth import verify_access, get_actor_from_claims
from hybrid import search_sops_vector, query_graph_entities, query_graph_edges
from db import (
    init_db,
    add_user,
    deactivate_user,
    get_active_users,
    get_user_stats,
    search_users,
    list_sops,
    get_sop,
    search_sops,
    list_system_logs,
    list_graph_entities,
    list_graph_edges,
    create_audit_log,
    create_approval_request,
    list_pending_approvals,
    update_approval_request,
    get_approval_request
)

app = Server("sqlite-mcp-server")

AUTH_SCHEMA = {
    "type": "object",
    "properties": {
        "token": {"type": "string", "description": "Bearer JWT access token."},
        "actor_id": {"type": "string", "description": "Optional actor identifier override."},
        "actor_role": {"type": "string", "description": "Optional actor role override."}
    },
    "required": ["token"]
}

TOOL_SCOPES = {
    "get_active_users": ["read:users"],
    "get_user_stats": ["read:users"],
    "search_users": ["read:users"],
    "add_user": ["write:users"],
    "deactivate_user": ["write:users"],
    "list_sops": ["read:sops"],
    "get_sop": ["read:sops"],
    "search_sops": ["read:sops"],
    "list_system_logs": ["read:logs"],
    "list_graph_entities": ["read:graph"],
    "list_graph_edges": ["read:graph"],
    "hybrid_query": ["read:hybrid"],
    "list_pending_approvals": ["read:approvals"],
    "review_approval_request": ["write:approvals"],
    "execute_approved_request": ["write:approvals"],
}

SENSITIVE_TOOLS = {"add_user", "deactivate_user"}


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List of all available tools."""
    return [
        Tool(
            name="get_active_users",
            description="Fetches all active users and their roles from the enterprise database.",
            inputSchema={"type": "object", "properties": {"auth": AUTH_SCHEMA}, "required": ["auth"]}
        ),
        Tool(
            name="add_user",
            description="Adds a new active user to the enterprise database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The full name of the user to add."},
                    "role": {"type": "string", "description": "Job role: Employee, Manager, Admin, Engineer, Intern, or Director. Defaults to Employee."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["name", "auth"]
            }
        ),
        Tool(
            name="deactivate_user",
            description="Deactivates an active user by their full name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The full name of the user to deactivate."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["name", "auth"]
            }
        ),
        Tool(
            name="get_user_stats",
            description="Returns a summary of total, active, and inactive user counts.",
            inputSchema={"type": "object", "properties": {"auth": AUTH_SCHEMA}, "required": ["auth"]}
        ),
        Tool(
            name="search_users",
            description="Searches users by a name fragment. Returns name, role, and status for all matches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A name fragment to search for."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["query", "auth"]
            }
        ),
        Tool(
            name="list_pending_approvals",
            description="Lists pending approval requests for sensitive tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of approvals to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["auth"]
            }
        ),
        Tool(
            name="list_sops",
            description="Lists SOPs with optional status and department filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Active, Draft, or Deprecated."},
                    "department": {"type": "string", "description": "Department filter."},
                    "limit": {"type": "integer", "description": "Maximum number of SOPs to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["auth"]
            }
        ),
        Tool(
            name="get_sop",
            description="Fetches a specific SOP by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sop_id": {"type": "integer", "description": "SOP ID."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["sop_id", "auth"]
            }
        ),
        Tool(
            name="search_sops",
            description="Searches SOPs by text query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "limit": {"type": "integer", "description": "Maximum number of SOPs to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["query", "auth"]
            }
        ),
        Tool(
            name="list_system_logs",
            description="Lists system logs with optional level and source filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {"type": "string", "description": "DEBUG, INFO, WARN, or ERROR."},
                    "source": {"type": "string", "description": "Log source filter."},
                    "limit": {"type": "integer", "description": "Maximum number of logs to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["auth"]
            }
        ),
        Tool(
            name="list_graph_entities",
            description="Lists knowledge graph entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Entity type filter."},
                    "limit": {"type": "integer", "description": "Maximum number of entities to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["auth"]
            }
        ),
        Tool(
            name="list_graph_edges",
            description="Lists edges connected to a graph entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "integer", "description": "Graph entity ID."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["entity_id", "auth"]
            }
        ),
        Tool(
            name="hybrid_query",
            description="Routes a query across SOPs, logs, or graph data and returns results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "User query to route."},
                    "limit": {"type": "integer", "description": "Maximum results to return."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["query", "auth"]
            }
        ),
        Tool(
            name="review_approval_request",
            description="Approve or reject a pending approval request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_id": {"type": "integer", "description": "Approval request ID."},
                    "status": {"type": "string", "description": "approved or rejected."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["request_id", "status", "auth"]
            }
        ),
        Tool(
            name="execute_approved_request",
            description="Executes a previously approved request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "request_id": {"type": "integer", "description": "Approved request ID to execute."},
                    "auth": AUTH_SCHEMA
                },
                "required": ["request_id", "auth"]
            }
        ),
    ]


def _authorize_tool(arguments: dict, tool_name: str) -> tuple[bool, dict, str, str, str | None]:
    auth = arguments.get("auth") or {}
    token = auth.get("token", "")
    required_scopes = TOOL_SCOPES.get(tool_name, [])
    ok, claims, error = verify_access(token, required_scopes)
    actor_id, actor_role = get_actor_from_claims(claims, auth)
    return ok, claims, actor_id, actor_role, error


def _route_hybrid_query(query: str) -> str:
    query_lower = (query or "").lower()
    if any(token in query_lower for token in ["relationship", "depends", "owns", "graph", "entity"]):
        return "graph"
    if any(token in query_lower for token in ["log", "error", "warning", "incident"]):
        return "logs"
    return "sops"


def _authorize_rest(request: Request, required_scopes: list[str]) -> tuple[bool, dict, str, str, str | None]:
    token = request.headers.get("authorization", "")
    ok, claims, error = verify_access(token, required_scopes)
    actor_id, actor_role = get_actor_from_claims(claims, {})
    return ok, claims, actor_id, actor_role, error


async def _handle_tool_call(request: Request) -> JSONResponse:
    body = await request.json()
    name = request.path_params.get("tool_name", "")
    arguments = body.get("arguments", {})
    if "auth" not in arguments and request.headers.get("authorization"):
        arguments["auth"] = {"token": request.headers.get("authorization")}
    result = await call_tool(name, arguments)
    content = result.content[0].text if result.content else "{}"
    return JSONResponse(json.loads(content))


async def _handle_pending_approvals(request: Request) -> JSONResponse:
    ok, _, actor_id, actor_role, error = _authorize_rest(request, ["read:approvals"])
    if not ok:
        return JSONResponse({"status": "error", "message": error or "Unauthorized."}, status_code=401)
    result = list_pending_approvals(limit=int(request.query_params.get("limit", "50")))
    create_audit_log(
        actor_id=actor_id,
        actor_role=actor_role,
        tool_name="list_pending_approvals",
        request_json=json.dumps({"limit": request.query_params.get("limit", "50")}),
        result_json=json.dumps(result),
        decision="allow"
    )
    return JSONResponse(result)


async def _handle_review_approval(request: Request) -> JSONResponse:
    ok, _, actor_id, actor_role, error = _authorize_rest(request, ["write:approvals"])
    if not ok:
        return JSONResponse({"status": "error", "message": error or "Unauthorized."}, status_code=401)
    body = await request.json()
    request_id = int(request.path_params.get("request_id", "0"))
    status = body.get("status", "")
    result = update_approval_request(request_id=request_id, status=status, reviewed_by=actor_id)
    create_audit_log(
        actor_id=actor_id,
        actor_role=actor_role,
        tool_name="review_approval_request",
        request_json=json.dumps({"request_id": request_id, "status": status}),
        result_json=json.dumps(result),
        decision="allow" if result.get("status") == "success" else "deny"
    )
    return JSONResponse(result)


async def _handle_health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle tool execution requests."""
    ok, claims, actor_id, actor_role, error = _authorize_tool(arguments, name)
    if not ok:
        result = {"status": "error", "message": error or "Unauthorized."}
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="deny"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    if name in SENSITIVE_TOOLS:
        approval_id = create_approval_request(
            tool_name=name,
            request_json=json.dumps(arguments),
            requested_by=actor_id,
            reason="Sensitive operation requires approval."
        )
        result = {
            "status": "pending_approval",
            "approval_request_id": approval_id,
            "message": "Approval required before execution."
        }
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="approve"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    if name == "get_active_users":
        data = get_active_users()
        result = data
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "add_user":
        result = add_user(name=arguments.get("name", ""), role=arguments.get("role", "Employee"))
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    elif name == "deactivate_user":
        result = deactivate_user(name=arguments.get("name", ""))
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    elif name == "get_user_stats":
        result = get_user_stats()
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "search_users":
        result = search_users(query=arguments.get("query", ""))
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "list_sops":
        result = list_sops(
            status=arguments.get("status"),
            department=arguments.get("department"),
            limit=arguments.get("limit", 50)
        )
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "get_sop":
        result = get_sop(sop_id=arguments.get("sop_id", 0))
        if result is None:
            result = {"status": "error", "message": "SOP not found."}
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow" if result.get("status") != "error" else "deny"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "search_sops":
        result = search_sops(query=arguments.get("query", ""), limit=arguments.get("limit", 50))
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "list_system_logs":
        result = list_system_logs(
            level=arguments.get("level"),
            source=arguments.get("source"),
            limit=arguments.get("limit", 100)
        )
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "list_graph_entities":
        result = list_graph_entities(
            entity_type=arguments.get("entity_type"),
            limit=arguments.get("limit", 100)
        )
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "list_graph_edges":
        entity_id = arguments.get("entity_id", 0)
        result = query_graph_edges(entity_id=entity_id, limit=100) or list_graph_edges(entity_id=entity_id)
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "hybrid_query":
        query = arguments.get("query", "")
        route = _route_hybrid_query(query)
        limit = arguments.get("limit", 25)
        if route == "graph":
            results = query_graph_entities(query=query, limit=limit) or list_graph_entities(limit=limit)
        elif route == "logs":
            results = list_system_logs(limit=limit)
        else:
            results = search_sops_vector(query=query, limit=limit) or search_sops(query=query, limit=limit)

        result = {"route": route, "results": results}
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "list_pending_approvals":
        result = list_pending_approvals(limit=arguments.get("limit", 50))
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, indent=2))])

    elif name == "review_approval_request":
        result = update_approval_request(
            request_id=arguments.get("request_id", 0),
            status=arguments.get("status", ""),
            reviewed_by=actor_id
        )
        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=name,
            request_json=json.dumps(arguments),
            result_json=json.dumps(result),
            decision="allow" if result.get("status") == "success" else "deny"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

    elif name == "execute_approved_request":
        approval = get_approval_request(arguments.get("request_id", 0))
        if not approval:
            result = {"status": "error", "message": "Approval request not found."}
            create_audit_log(
                actor_id=actor_id,
                actor_role=actor_role,
                tool_name=name,
                request_json=json.dumps(arguments),
                result_json=json.dumps(result),
                decision="deny"
            )
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

        if approval.get("status") != "approved":
            result = {"status": "error", "message": "Approval request is not approved."}
            create_audit_log(
                actor_id=actor_id,
                actor_role=actor_role,
                tool_name=name,
                request_json=json.dumps(arguments),
                result_json=json.dumps(result),
                decision="deny"
            )
            return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

        tool_name = approval.get("tool_name")
        tool_args = approval.get("request", {})

        if tool_name == "add_user":
            result = add_user(name=tool_args.get("name", ""), role=tool_args.get("role", "Employee"))
        elif tool_name == "deactivate_user":
            result = deactivate_user(name=tool_args.get("name", ""))
        else:
            result = {"status": "error", "message": "Unsupported approved tool."}

        create_audit_log(
            actor_id=actor_id,
            actor_role=actor_role,
            tool_name=f"execute:{tool_name}",
            request_json=json.dumps({"approval_id": approval.get("id"), "tool": tool_name}),
            result_json=json.dumps(result),
            decision="allow" if result.get("status") != "error" else "deny"
        )
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(result))])

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
        ),
        Resource(
            uri="sops://catalog",
            name="SOP Catalog",
            description="Structured SOP summaries for operational reference.",
            mimeType="application/json"
        ),
        Resource(
            uri="logs://recent",
            name="Recent System Logs",
            description="Recent system logs across critical services.",
            mimeType="application/json"
        ),
        Resource(
            uri="graph://entities",
            name="Knowledge Graph Entities",
            description="Entity nodes from the operations knowledge graph.",
            mimeType="application/json"
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
    if uri == "sops://catalog":
        return json.dumps(list_sops(limit=25), indent=2)
    if uri == "logs://recent":
        return json.dumps(list_system_logs(limit=50), indent=2)
    if uri == "graph://entities":
        return json.dumps(list_graph_entities(limit=50), indent=2)
    raise ValueError(f"Unknown resource: {uri}")


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    """Expose available system prompts."""
    return [
        Prompt(
            name="hr-assistant",
            description="A system prompt configuring the AI to act as a helpful enterprise HR assistant.",
            arguments=[]
        ),
        Prompt(
            name="ops-assistant",
            description="Dynamic ops assistant prompt tailored to role and incident state.",
            arguments=[
                {"name": "role", "description": "User role such as Analyst, Manager, or Admin."},
                {"name": "incident_level", "description": "None, Sev1, Sev2, or Sev3."}
            ]
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
    if name == "ops-assistant":
        role = (arguments or {}).get("role", "Analyst")
        incident_level = (arguments or {}).get("incident_level", "None")
        return GetPromptResult(
            description="Operations assistant context with role and incident awareness.",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            "You are an operations assistant for an enterprise control room. "
                            f"Current user role: {role}. Incident level: {incident_level}. "
                            "Use MCP tools to retrieve SOPs, logs, and graph relationships. "
                            "If a sensitive action is requested, create an approval request and wait."
                        )
                    )
                )
            ]
        )
    raise ValueError(f"Unknown prompt: {name}")


async def main():
    init_db()
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
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/api/tools/{tool_name}", endpoint=_handle_tool_call, methods=["POST"]),
            Route("/api/approvals", endpoint=_handle_pending_approvals, methods=["GET"]),
            Route("/api/approvals/{request_id}", endpoint=_handle_review_approval, methods=["POST"]),
            Route("/health", endpoint=_handle_health, methods=["GET"])
        ])

        uvicorn.run(starlette_app, host="0.0.0.0", port=args.port)
    else:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
