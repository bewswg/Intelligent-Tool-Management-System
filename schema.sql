-- schema.sql
DROP TABLE IF EXISTS tools;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS projects;

-- Users Table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    contact_id TEXT
);

-- Tools Table
CREATE TABLE tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    current_holder TEXT,
    calibration_due TEXT,
    total_checkouts INTEGER DEFAULT 0,
    total_usage_hours REAL DEFAULT 0.0
);

-- Transactions Table
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    type TEXT NOT NULL, -- 'checkout' or 'checkin'
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(tool_id) REFERENCES tools(id)
);

-- Audit Log Table
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    action TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Projects Table (NEW)
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    briefing TEXT NOT NULL,
    tool_list TEXT NOT NULL -- JSON array of tool IDs
);