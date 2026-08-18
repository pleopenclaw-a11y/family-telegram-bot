"""SQLite local adapter for the Family Board domain layer.

Design notes (Track A):
  * The backing store is the *existing* `memories` table, so legacy
    search/delete behavior (see family_memory.py) keeps working and no
    existing data is migrated or lost.
  * Notes/events/tasks/shopping are written into `memories` with a stable
    `kind` value, reusing the column that the Telegram bot and extractor
    already understand.
  * Boards need a few extra fields (event datetime, task done, shopping
    qty/purchased) that the legacy row does not carry. These live in an
    additive side table `entity_data` keyed by the `memories.id`. It is
    created with CREATE TABLE IF NOT EXISTS, so opening a pre-existing
    database is never destructive.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domain import Event, Note, ShoppingItem, Task

# kind values stored in the legacy `memories.kind` column.
KIND_NOTE = "note"
KIND_EVENT = "event"
KIND_TASK = "task"
KIND_SHOPPING = "shopping"

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteFamilyStore:
    """Typed CRUD over the existing memories table plus a board side table."""

    def __init__(self, db_path: str | Path) -> None:
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT,
                user_name TEXT,
                kind TEXT NOT NULL DEFAULT 'note',
                text TEXT NOT NULL,
                source_message_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_group_kind
                ON memories(group_id, kind);
            CREATE TABLE IF NOT EXISTS entity_data (
                memory_id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
            );
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # ---- internal helpers -----------------------------------------------

    def _insert(self, group_id: str, kind: str, text: str, payload: dict[str, Any]) -> int:
        now = _now_iso()
        with self._db:
            cur = self._db.execute(
                "INSERT INTO memories (group_id, kind, text, created_at) VALUES (?,?,?,?)",
                (group_id, kind, text, now),
            )
            m_id = int(cur.lastrowid)
            self._db.execute(
                "INSERT INTO entity_data (memory_id, entity_type, payload) VALUES (?,?,?)",
                (m_id, kind, json.dumps(payload, ensure_ascii=False)),
            )
        return m_id

    def _board_composites(self, group_id: str, kind: str) -> list[tuple[sqlite3.Row, sqlite3.Row]]:
        """Return (memory_row, entity_row) pairs for a kind, newest first."""
        rows = self._db.execute(
            """
            SELECT m.*, e.entity_type, e.payload
            FROM memories m
            LEFT JOIN entity_data e ON e.memory_id = m.id
            WHERE m.group_id = ? AND m.kind = ?
            ORDER BY m.created_at DESC, m.id DESC
            """,
            (group_id, kind),
        ).fetchall()
        return [(r, r) for r in rows]

    def _payload(self, entity_row: sqlite3.Row) -> dict[str, Any]:
        raw = entity_row["payload"]
        if raw is None:
            return {}
        return json.loads(raw)

    def _legacy_id(self, m_row: sqlite3.Row) -> int:
        return int(m_row["id"])

    # ---- Notes ----------------------------------------------------------

    def create_note(self, group_id: str, note: Note) -> int:
        m_id = self._insert(group_id, KIND_NOTE, note.body, {"title": note.title, "body": note.body})
        return m_id

    def get_note(self, group_id: str, note_id: int) -> Note | None:
        for m, e in self._board_composites(group_id, KIND_NOTE):
            if self._legacy_id(m) == note_id:
                p = self._payload(e)
                return Note(title=p.get("title") or m["text"], body=p.get("body") or m["text"],
                            id=note_id, legacy_id=self._legacy_id(m), created_at=m["created_at"])
        return None

    def list_notes(self, group_id: str) -> list[Note]:
        return [self.get_note(group_id, self._legacy_id(m)) for m, _ in self._board_composites(group_id, KIND_NOTE)]

    def delete_note(self, group_id: str, note_id: int) -> bool:
        with self._db:
            cur = self._db.execute("DELETE FROM memories WHERE id = ? AND group_id = ? AND kind = ?",
                                   (note_id, group_id, KIND_NOTE))
            return cur.rowcount > 0

    # ---- Events ---------------------------------------------------------

    def create_event(self, group_id: str, event: Event) -> int:
        return self._insert(group_id, KIND_EVENT, event.title, {"title": event.title, "at": event.at})

    def get_event(self, group_id: str, event_id: int) -> Event | None:
        for m, e in self._board_composites(group_id, KIND_EVENT):
            if self._legacy_id(m) == event_id:
                p = self._payload(e)
                return Event(title=p.get("title") or m["text"], at=p.get("at", ""),
                             id=event_id, legacy_id=self._legacy_id(m), created_at=m["created_at"])
        return None

    def list_events(self, group_id: str, upcoming_only: bool = False) -> list[Event]:
        events = [self.get_event(group_id, self._legacy_id(m)) for m, _ in self._board_composites(group_id, KIND_EVENT)]
        events = [e for e in events if e is not None]
        if upcoming_only:
            now = _now_iso()
            events = [e for e in events if e.at >= now]
        return events

    # ---- Tasks ----------------------------------------------------------

    def create_task(self, group_id: str, task: Task) -> int:
        return self._insert(group_id, KIND_TASK, task.title, {"title": task.title, "done": task.done})

    def get_task(self, group_id: str, task_id: int) -> Task | None:
        for m, e in self._board_composites(group_id, KIND_TASK):
            if self._legacy_id(m) == task_id:
                p = self._payload(e)
                return Task(title=p.get("title") or m["text"], done=bool(p.get("done", False)),
                            id=task_id, legacy_id=self._legacy_id(m), created_at=m["created_at"])
        return None

    def set_task_done(self, group_id: str, task_id: int, done: bool) -> bool:
        task = self.get_task(group_id, task_id)
        if task is None:
            return False
        with self._db:
            cur = self._db.execute(
                "UPDATE entity_data SET payload = ? WHERE memory_id = ?",
                (json.dumps({"title": task.title, "done": done}, ensure_ascii=False), task_id),
            )
        return cur.rowcount > 0

    def list_tasks(self, group_id: str, open_only: bool = False) -> list[Task]:
        tasks = [self.get_task(group_id, self._legacy_id(m)) for m, _ in self._board_composites(group_id, KIND_TASK)]
        tasks = [t for t in tasks if t is not None]
        if open_only:
            tasks = [t for t in tasks if not t.done]
        return tasks

    # ---- Shopping -------------------------------------------------------

    def create_shopping_item(self, group_id: str, item: ShoppingItem) -> int:
        return self._insert(group_id, KIND_SHOPPING, item.name,
                            {"name": item.name, "qty": item.qty, "purchased": item.purchased})

    def get_shopping_item(self, group_id: str, item_id: int) -> ShoppingItem | None:
        for m, e in self._board_composites(group_id, KIND_SHOPPING):
            if self._legacy_id(m) == item_id:
                p = self._payload(e)
                return ShoppingItem(name=p.get("name") or m["text"],
                                    qty=int(p.get("qty", 1)),
                                    purchased=bool(p.get("purchased", False)),
                                    id=item_id, legacy_id=self._legacy_id(m), created_at=m["created_at"])
        return None

    def set_shopping_purchased(self, group_id: str, item_id: int, purchased: bool) -> bool:
        item = self.get_shopping_item(group_id, item_id)
        if item is None:
            return False
        with self._db:
            cur = self._db.execute(
                "UPDATE entity_data SET payload = ? WHERE memory_id = ?",
                (json.dumps({"name": item.name, "qty": item.qty, "purchased": purchased}, ensure_ascii=False),
                 item_id),
            )
        return cur.rowcount > 0

    def list_shopping(self, group_id: str, open_only: bool = False) -> list[ShoppingItem]:
        items = [self.get_shopping_item(group_id, self._legacy_id(m)) for m, _ in self._board_composites(group_id, KIND_SHOPPING)]
        items = [i for i in items if i is not None]
        if open_only:
            items = [i for i in items if not i.purchased]
        return items

    # ---- Legacy compatibility -------------------------------------------

    def legacy_add(self, group_id: str, text: str, kind: str = "note",
                   user_id: str | None = None, user_name: str | None = None,
                   source_message_id: int | None = None) -> int:
        now = _now_iso()
        with self._db:
            cur = self._db.execute(
                "INSERT INTO memories (group_id,user_id,user_name,kind,text,source_message_id,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (group_id, user_id, user_name, kind, text, source_message_id, now),
            )
        return int(cur.lastrowid)

    def legacy_search(self, group_id: str, term: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM memories WHERE group_id = ? AND text LIKE ? ORDER BY created_at DESC LIMIT ?",
            (group_id, f"%{term}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def legacy_delete(self, memory_id: int, group_id: str) -> bool:
        with self._db:
            cur = self._db.execute("DELETE FROM memories WHERE id = ? AND group_id = ?", (memory_id, group_id))
        return cur.rowcount > 0