from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

def database_path() -> Path:
    return Path(os.getenv("FAMILY_BOARD_DB_PATH", Path(__file__).resolve().parent.parent / "family_memory.sqlite3"))


DB_PATH = database_path()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT,
            user_name TEXT,
            kind TEXT NOT NULL DEFAULT 'note',
            text TEXT NOT NULL,
            source_message_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_memories_group_created ON memories(group_id, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_memories_group_kind ON memories(group_id, kind)")
    db.commit()
    return db


def add_memory(group_id: str, text: str, user_id: str | None = None, user_name: str | None = None,
               kind: str = "note", source_message_id: int | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cur = db.execute(
            "INSERT INTO memories (group_id,user_id,user_name,kind,text,source_message_id,created_at) VALUES (?,?,?,?,?,?,?)",
            (group_id, user_id, user_name, kind, text, source_message_id, now),
        )
        return int(cur.lastrowid)


def list_memories(group_id: str, since: datetime | None = None, kind: str | None = None, limit: int = 30):
    query = "SELECT * FROM memories WHERE group_id = ?"
    params: list[object] = [group_id]
    if since:
        query += " AND created_at >= ?"
        params.append(since.astimezone(timezone.utc).isoformat())
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connect() as db:
        return db.execute(query, params).fetchall()


def search_memories(group_id: str, term: str, limit: int = 30):
    with connect() as db:
        return db.execute(
            "SELECT * FROM memories WHERE group_id = ? AND text LIKE ? ORDER BY created_at DESC LIMIT ?",
            (group_id, f"%{term}%", limit),
        ).fetchall()


def delete_memory(memory_id: int, group_id: str) -> bool:
    with connect() as db:
        cur = db.execute("DELETE FROM memories WHERE id = ? AND group_id = ?", (memory_id, group_id))
        return cur.rowcount > 0


def find_delete_candidates(group_id: str, term: str, limit: int = 10):
    return search_memories(group_id, term, limit)


def utc_days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)
