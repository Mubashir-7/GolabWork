"""
Database setup and connection management.

Uses SQLite for simplicity. All database access goes through get_db().
"""

import sqlite3
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "events.db")


def get_db() -> sqlite3.Connection:
    """Get a database connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables. Safe to call multiple times."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            payload TEXT NOT NULL,
            user_id TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def reset_db():
    """Drop and recreate all tables. Used in tests only."""
    conn = get_db()
    conn.execute("DROP TABLE IF EXISTS events")
    conn.commit()
    conn.close()
    init_db()
