-- Enterprise Data Agent — SQLite Schema
-- Run with: sqlite3 enterprise_data.db < schema.sql

CREATE TABLE IF NOT EXISTS users (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT    NOT NULL,
    role   TEXT    NOT NULL DEFAULT 'Employee',
    status TEXT    NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Inactive'))
);

CREATE TABLE IF NOT EXISTS sops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    department  TEXT    NOT NULL,
    owner       TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Draft', 'Deprecated')),
    content     TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS system_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,
    level       TEXT    NOT NULL
        CHECK (level IN ('DEBUG', 'INFO', 'WARN', 'ERROR')),
    message     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS graph_entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    attributes_json TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity_id  INTEGER NOT NULL,
    to_entity_id    INTEGER NOT NULL,
    relation_type   TEXT    NOT NULL,
    attributes_json TEXT    NOT NULL DEFAULT '{}',
    FOREIGN KEY (from_entity_id) REFERENCES graph_entities(id),
    FOREIGN KEY (to_entity_id) REFERENCES graph_entities(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id     TEXT    NOT NULL,
    actor_role   TEXT    NOT NULL,
    tool_name    TEXT    NOT NULL,
    request_json TEXT    NOT NULL,
    result_json  TEXT    NOT NULL,
    decision     TEXT    NOT NULL DEFAULT 'allow'
        CHECK (decision IN ('allow', 'deny', 'approve', 'reject')),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name    TEXT    NOT NULL,
    request_json TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    requested_by TEXT    NOT NULL,
    reason       TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    reviewed_by  TEXT    NULL,
    reviewed_at  TEXT    NULL
);

-- Seed data
INSERT OR IGNORE INTO users (id, name, role, status) VALUES
    (1, 'Alice Smith',    'Admin',    'Active'),
    (2, 'Bob Jones',      'Engineer', 'Inactive'),
    (3, 'Charlie Brown',  'Manager',  'Active'),
    (4, 'Upeka',          'Employee', 'Active');

INSERT OR IGNORE INTO sops (id, title, department, owner, status, content, updated_at) VALUES
    (1, 'Incident Response - Severity 1', 'Security', 'Alice Smith', 'Active',
     '1) Declare incident. 2) Assemble war room. 3) Contain blast radius. 4) Notify stakeholders. 5) Postmortem within 48 hours.',
     datetime('now')),
    (2, 'Employee Offboarding', 'PeopleOps', 'Charlie Brown', 'Active',
     '1) Disable access. 2) Recover assets. 3) Conduct exit interview. 4) Update HRIS records.',
     datetime('now')),
    (3, 'Quarterly Access Review', 'Compliance', 'Alice Smith', 'Draft',
     '1) Export access lists. 2) Review for anomalies. 3) Revoke stale access. 4) Archive evidence.',
     datetime('now'));

INSERT OR IGNORE INTO system_logs (id, source, level, message, created_at) VALUES
    (1, 'auth-service', 'INFO', 'OAuth token issued for user Alice Smith', datetime('now')),
    (2, 'mcp-server', 'WARN', 'Tool call rate limit at 80% threshold', datetime('now')),
    (3, 'graph-sync', 'ERROR', 'Neo4j sync failed for entity SYS-4431', datetime('now'));

INSERT OR IGNORE INTO graph_entities (id, entity_type, name, attributes_json) VALUES
    (1, 'System', 'Payroll API', '{"owner":"PeopleOps","tier":"critical"}'),
    (2, 'SOP', 'Incident Response - Severity 1', '{"department":"Security"}'),
    (3, 'Team', 'Security Operations', '{"lead":"Alice Smith"}'),
    (4, 'Service', 'Auth Service', '{"owner":"Platform"}');

INSERT OR IGNORE INTO graph_edges (id, from_entity_id, to_entity_id, relation_type, attributes_json) VALUES
    (1, 3, 1, 'owns', '{"confidence":0.92}'),
    (2, 2, 3, 'authored_by', '{"since":"2024-11-10"}'),
    (3, 4, 1, 'depends_on', '{"latency_ms":120}');
