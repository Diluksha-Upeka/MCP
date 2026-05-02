"""
LangGraph demo workflow calling MCP REST tools in a multi-step loop.
"""
import os
import json
import httpx
from typing import TypedDict

from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    query: str
    route: str
    context: list[dict]
    result: dict


MCP_API_URL = os.getenv("MCP_API_URL", "http://localhost:8000/api")
MCP_TOKEN = os.getenv("MCP_TOKEN", "")


def _call_tool(name: str, arguments: dict) -> dict:
    headers = {"Authorization": f"Bearer {MCP_TOKEN}"} if MCP_TOKEN else {}
    payload = {"arguments": arguments}
    url = f"{MCP_API_URL}/tools/{name}"
    with httpx.Client(timeout=20) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def classify(state: AgentState) -> AgentState:
    query = state["query"].lower()
    if any(token in query for token in ["incident", "error", "log"]):
        state["route"] = "logs"
    elif any(token in query for token in ["relationship", "depends", "owner", "graph"]):
        state["route"] = "graph"
    else:
        state["route"] = "sops"
    return state


def gather_context(state: AgentState) -> AgentState:
    if state["route"] == "logs":
        result = _call_tool("list_system_logs", {"limit": 10, "auth": {"token": f"Bearer {MCP_TOKEN}"}})
    elif state["route"] == "graph":
        result = _call_tool("list_graph_entities", {"limit": 10, "auth": {"token": f"Bearer {MCP_TOKEN}"}})
    else:
        result = _call_tool("search_sops", {"query": state["query"], "limit": 5, "auth": {"token": f"Bearer {MCP_TOKEN}"}})
    state["context"] = result if isinstance(result, list) else result.get("results", [])
    return state


def act(state: AgentState) -> AgentState:
    result = _call_tool("hybrid_query", {"query": state["query"], "limit": 5, "auth": {"token": f"Bearer {MCP_TOKEN}"}})
    state["result"] = result
    return state


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("gather_context", gather_context)
    graph.add_node("act", act)
    graph.set_entry_point("classify")
    graph.add_edge("classify", "gather_context")
    graph.add_edge("gather_context", "act")
    graph.add_edge("act", END)
    return graph


def main() -> None:
    if not MCP_TOKEN:
        raise SystemExit("Set MCP_TOKEN before running the demo.")
    query = os.getenv("MCP_DEMO_QUERY", "Show me the incident response SOP")
    graph = build_graph().compile()
    result = graph.invoke({"query": query, "route": "", "context": [], "result": {}})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
