"""
db.py — Shared database access layer.

Both app.py (Streamlit frontend) and server.py (MCP stdio server) import
from this module to avoid duplicating SQL logic.
"""
import os
import sqlite3
import json

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'enterprise_data.db'))
SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'schema.sql'))


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Initialize database file from schema.sql if missing."""
    if os.path.exists(DB_PATH):
        return
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError("schema.sql not found for DB initialization")
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
    conn.commit()
    conn.close()


# Validation helpers

def _validate_name(name: str) -> str | None:
    """Returns error message string if invalid, else None."""
    if not name or not isinstance(name, str):
        return "Name is required."
    name = name.strip()
    if len(name) < 2:
        return "Name must be at least 2 characters."
    if len(name) > 100:
        return "Name must be 100 characters or fewer."
    return None

def _validate_role(role: str) -> str | None:
    allowed = {"Employee", "Manager", "Admin", "Engineer", "Intern", "Director"}
    if role not in allowed:
        return f"Role must be one of: {', '.join(sorted(allowed))}."
    return None

def _validate_limit(limit: int, max_limit: int = 200) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return max_limit
    if value < 1:
        return 1
    if value > max_limit:
        return max_limit
    return value


# Query functions

def get_active_users() -> list[dict]:
    """Returns all active users with their roles."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT name, role FROM users WHERE status = 'Active' ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [{"name": row[0], "role": row[1]} for row in rows]


def add_user(name: str, role: str = "Employee") -> dict:
    """Adds a new active user. Returns a status dict."""
    name = (name or "").strip()
    role = (role or "Employee").strip()

    err = _validate_name(name)
    if err:
        return {"status": "error", "message": err}
    err = _validate_role(role)
    if err:
        return {"status": "error", "message": err}

    conn = _connect()
    cur = conn.cursor()
    # Check for duplicate
    cur.execute("SELECT id FROM users WHERE name = ? AND status = 'Active'", (name,))
    if cur.fetchone():
        conn.close()
        return {"status": "error", "message": f"An active user named '{name}' already exists."}

    cur.execute(
        "INSERT INTO users (name, role, status) VALUES (?, ?, 'Active')",
        (name, role)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"User '{name}' added as {role}."}


def deactivate_user(name: str) -> dict:
    """Sets a user's status to Inactive. Returns a status dict."""
    name = (name or "").strip()
    err = _validate_name(name)
    if err:
        return {"status": "error", "message": err}

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET status = 'Inactive' WHERE name = ? AND status = 'Active'",
        (name,)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        return {"status": "error", "message": f"No active user named '{name}' found."}
    return {"status": "success", "message": f"User '{name}' has been deactivated."}


def get_user_stats() -> dict:
    """Returns total, active, and inactive user counts."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) FROM users GROUP BY status")
    rows = cur.fetchall()
    conn.close()
    counts = {row[0]: row[1] for row in rows}
    return {
        "total":    sum(counts.values()),
        "active":   counts.get("Active", 0),
        "inactive": counts.get("Inactive", 0),
    }


def search_users(query: str) -> list[dict]:
    """Searches users by name fragment (case-insensitive). Returns matching users."""
    query = (query or "").strip()
    if not query:
        return []
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT name, role, status FROM users WHERE name LIKE ? ORDER BY name",
        (f"%{query}%",)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"name": r[0], "role": r[1], "status": r[2]} for r in rows]


# SOPs

def list_sops(status: str | None = None, department: str | None = None, limit: int = 50) -> list[dict]:
    """Returns SOPs filtered by status/department."""
    limit = _validate_limit(limit)
    filters = []
    params: list[str] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    if department:
        filters.append("department = ?")
        params.append(department)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, title, department, owner, status, updated_at FROM sops {where_clause} ORDER BY updated_at DESC LIMIT ?",
        (*params, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "department": r[2], "owner": r[3], "status": r[4], "updated_at": r[5]}
        for r in rows
    ]


def get_sop(sop_id: int) -> dict | None:
    """Returns a single SOP by ID."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, department, owner, status, content, updated_at FROM sops WHERE id = ?",
        (sop_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "department": row[2],
        "owner": row[3],
        "status": row[4],
        "content": row[5],
        "updated_at": row[6],
    }


def search_sops(query: str, limit: int = 50) -> list[dict]:
    """Search SOPs by title or content."""
    query = (query or "").strip()
    if not query:
        return []
    limit = _validate_limit(limit)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, department, owner, status, updated_at FROM sops WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT ?",
        (f"%{query}%", f"%{query}%", limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "title": r[1], "department": r[2], "owner": r[3], "status": r[4], "updated_at": r[5]}
        for r in rows
    ]


# System logs

def list_system_logs(level: str | None = None, source: str | None = None, limit: int = 100) -> list[dict]:
    """Returns system logs filtered by level/source."""
    limit = _validate_limit(limit)
    filters = []
    params: list[str] = []
    if level:
        filters.append("level = ?")
        params.append(level)
    if source:
        filters.append("source = ?")
        params.append(source)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, source, level, message, created_at FROM system_logs {where_clause} ORDER BY created_at DESC LIMIT ?",
        (*params, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "source": r[1], "level": r[2], "message": r[3], "created_at": r[4]}
        for r in rows
    ]


# Knowledge graph

def list_graph_entities(entity_type: str | None = None, limit: int = 100) -> list[dict]:
    """Returns graph entities, optionally filtered by type."""
    limit = _validate_limit(limit)
    conn = _connect()
    cur = conn.cursor()
    if entity_type:
        cur.execute(
            "SELECT id, entity_type, name, attributes_json FROM graph_entities WHERE entity_type = ? ORDER BY name LIMIT ?",
            (entity_type, limit)
        )
    else:
        cur.execute(
            "SELECT id, entity_type, name, attributes_json FROM graph_entities ORDER BY name LIMIT ?",
            (limit,)
        )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "entity_type": r[1], "name": r[2], "attributes": json.loads(r[3] or "{}")}
        for r in rows
    ]


def list_graph_edges(entity_id: int) -> list[dict]:
    """Returns edges connected to the given entity."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, from_entity_id, to_entity_id, relation_type, attributes_json FROM graph_edges WHERE from_entity_id = ? OR to_entity_id = ?",
        (entity_id, entity_id)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "from_entity_id": r[1],
            "to_entity_id": r[2],
            "relation_type": r[3],
            "attributes": json.loads(r[4] or "{}")
        }
        for r in rows
    ]


# Audit logging and approvals

def create_audit_log(
    actor_id: str,
    actor_role: str,
    tool_name: str,
    request_json: str,
    result_json: str,
    decision: str = "allow"
) -> None:
    """Writes an audit log record for a tool invocation."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_logs (actor_id, actor_role, tool_name, request_json, result_json, decision) VALUES (?, ?, ?, ?, ?, ?)",
        (actor_id, actor_role, tool_name, request_json, result_json, decision)
    )
    conn.commit()
    conn.close()


def create_approval_request(tool_name: str, request_json: str, requested_by: str, reason: str = "") -> int:
    """Creates a new approval request and returns its ID."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO approval_requests (tool_name, request_json, requested_by, reason) VALUES (?, ?, ?, ?)",
        (tool_name, request_json, requested_by, reason)
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(request_id)


def list_pending_approvals(limit: int = 50) -> list[dict]:
    """Returns pending approval requests."""
    limit = _validate_limit(limit)
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, tool_name, request_json, status, requested_by, reason, created_at FROM approval_requests WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "tool_name": r[1],
            "request": json.loads(r[2] or "{}"),
            "status": r[3],
            "requested_by": r[4],
            "reason": r[5],
            "created_at": r[6]
        }
        for r in rows
    ]


def update_approval_request(request_id: int, status: str, reviewed_by: str) -> dict:
    """Updates approval request status."""
    if status not in {"approved", "rejected", "expired"}:
        return {"status": "error", "message": "Invalid status."}
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE approval_requests SET status = ?, reviewed_by = ?, reviewed_at = datetime('now') WHERE id = ?",
        (status, reviewed_by, request_id)
    )
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        return {"status": "error", "message": "Approval request not found."}
    return {"status": "success", "message": f"Approval request {request_id} marked {status}."}


def get_approval_request(request_id: int) -> dict | None:
    """Returns an approval request by ID."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, tool_name, request_json, status, requested_by, reason, created_at, reviewed_by, reviewed_at FROM approval_requests WHERE id = ?",
        (request_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "tool_name": row[1],
        "request": json.loads(row[2] or "{}"),
        "status": row[3],
        "requested_by": row[4],
        "reason": row[5],
        "created_at": row[6],
        "reviewed_by": row[7],
        "reviewed_at": row[8]
    }
