"""
db.py — Shared database access layer.

Both app.py (Streamlit frontend) and server.py (MCP stdio server) import
from this module to avoid duplicating SQL logic.
"""
import os
import sqlite3
import json

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'enterprise_data.db'))


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


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
