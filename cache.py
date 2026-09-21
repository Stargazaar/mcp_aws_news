"""
cache.py
SQLite-backed cache with TTL for RSS feed results.
No external dependencies — uses Python's built-in sqlite3.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "cache.db"
DEFAULT_TTL_SECONDS = 3600  # 1 hour


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key        TEXT PRIMARY KEY,
            fetched_at REAL NOT NULL,
            query_str  TEXT NOT NULL,
            data_json  TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def make_key(q: str, weeks_back: int) -> str:
    """Deterministic cache key from query + time window."""
    raw = f"{q.lower().strip()}|{weeks_back}"
    return hashlib.md5(raw.encode()).hexdigest()


def get(key: str, ttl: int = DEFAULT_TTL_SECONDS) -> Optional[list]:
    """Return cached data if it exists and is within TTL, else None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT fetched_at, data_json FROM cache WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return None
    fetched_at, data_json = row
    if time.time() - fetched_at > ttl:
        return None  # expired
    return json.loads(data_json)


def set(key: str, query_str: str, data: list) -> None:
    """Write or overwrite a cache entry."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, fetched_at, query_str, data_json) "
            "VALUES (?, ?, ?, ?)",
            (key, time.time(), query_str, json.dumps(data)),
        )


def list_entries() -> list[dict]:
    """Return all cache entries with human-readable timestamps."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT key, query_str, fetched_at FROM cache ORDER BY fetched_at DESC"
        ).fetchall()
    return [
        {
            "key": r[0][:8] + "...",
            "query": r[1],
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[2])),
            "age_minutes": round((time.time() - r[2]) / 60, 1),
        }
        for r in rows
    ]


def clear_all() -> int:
    """Delete all cache entries. Returns count of deleted rows."""
    with _conn() as conn:
        n = conn.execute("DELETE FROM cache").rowcount
    return n
