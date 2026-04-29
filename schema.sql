-- Enterprise Data Agent — SQLite Schema
-- Run with: sqlite3 enterprise_data.db < schema.sql

CREATE TABLE IF NOT EXISTS users (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT    NOT NULL,
    role   TEXT    NOT NULL DEFAULT 'Employee',
    status TEXT    NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Inactive'))
);

-- Seed data
INSERT OR IGNORE INTO users (id, name, role, status) VALUES
    (1, 'Alice Smith',    'Admin',    'Active'),
    (2, 'Bob Jones',      'Engineer', 'Inactive'),
    (3, 'Charlie Brown',  'Manager',  'Active'),
    (4, 'Upeka',          'Employee', 'Active');
