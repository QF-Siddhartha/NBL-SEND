"""Database helpers for Helpdesk LAN (SQLite)."""
import sqlite3
from datetime import datetime

from flask import current_app, g

TIME_FMT = "%Y-%m-%d %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_no       TEXT UNIQUE,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    name            TEXT NOT NULL,
    department      TEXT NOT NULL,
    phone           TEXT NOT NULL DEFAULT '',
    location        TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'Medium',
    subject         TEXT NOT NULL,
    description     TEXT NOT NULL,
    attachment_name TEXT,
    attachment_file TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    answer          TEXT NOT NULL DEFAULT '',
    published       INTEGER NOT NULL DEFAULT 1,
    viewed          INTEGER NOT NULL DEFAULT 0,
    in_progress_at  TEXT,
    resolved_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

CREATE TABLE IF NOT EXISTS ticket_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    action     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_log_ticket ON ticket_log(ticket_id);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    text       TEXT NOT NULL,
    author     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_ticket ON notes(ticket_id);

CREATE TABLE IF NOT EXISTS admins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_login      TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT
);
"""


def now():
    """Current local server time as a sortable string."""
    return datetime.now().strftime(TIME_FMT)


def parse_time(value):
    return datetime.strptime(value, TIME_FMT) if value else None


def connect(path):
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path):
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """One connection per request, closed automatically afterwards."""
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def add_log(conn, ticket_id, action):
    conn.execute(
        "INSERT INTO ticket_log (ticket_id, action, created_at) VALUES (?, ?, ?)",
        (ticket_id, action, now()),
    )
