"""Track C — server-side domain/action boundary for the Family Board and Telegram.

This module is the single confirmed-authority for structured actions. Both the
HTTP API (``api_server``) and any future Telegram caller go through these
functions so that no write path duplicates persistence logic.

Confirmation-safe action protocol
---------------------------------
1. ``preview_capture`` — run the 9arm extractor to classify raw text into a
   structured draft. **No side effects**: nothing is persisted, so the caller
   can show a preview and ask for confirmation safely.
2. ``confirm_capture`` — the caller (user, via HTTP or Telegram) explicitly
   confirms the draft. This is the only step that writes to the database.

The 9arm API key is consumed only inside ``preview_capture``/``commit_capture``
through the injected :class:`~ninearm_client.NineArmClient`; it is never part of
a returned payload, and never exposed through any endpoint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import family_memory as store
from extractor import Extraction, extract_message
from ninearm_client import NineArmClient

ALLOWED_KINDS = {"event", "expense", "task", "note"}


@dataclass(frozen=True)
class PreviewResult:
    """A non-persisted, confirmation-safe view of a captured message."""

    text: str
    action: str  # "save" | "ignore" | "confirm"
    kind: str
    normalized_text: str
    confidence: float
    question: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommitResult:
    """Result of an explicit, confirmed write to the board store."""

    id: int
    group_id: str
    kind: str
    normalized_text: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def preview_capture(
    client: NineArmClient,
    text: str,
    *,
    extract=extract_message,
) -> PreviewResult:
    """Classify ``text`` into a structured draft without persisting anything.

    Returns a :class:`PreviewResult`. No database write happens here, so
    callers can safely show the preview and ask for explicit confirmation.
    """
    extraction: Extraction = extract(client, text)
    return PreviewResult(
        text=text,
        action=extraction.action,
        kind=extraction.kind,
        normalized_text=extraction.normalized_text,
        confidence=extraction.confidence,
        question=extraction.question,
    )


def commit_capture(
    group_id: str,
    *,
    kind: str,
    normalized_text: str,
    user_id: str | None = None,
    user_name: str | None = None,
    source_message_id: int | None = None,
) -> CommitResult:
    """Persist an explicitly confirmed capture.

    Callers must only invoke this after the user has confirmed a preview. It is
    the single write path shared by Telegram and the HTTP API.
    """
    kind = kind if kind in ALLOWED_KINDS else "note"
    memory_id = store.add_memory(
        group_id,
        normalized_text,
        user_id=user_id,
        user_name=user_name,
        kind=kind,
        source_message_id=source_message_id,
    )
    return CommitResult(
        id=memory_id,
        group_id=group_id,
        kind=kind,
        normalized_text=normalized_text,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def get_board(
    group_id: str,
    *,
    today=None,
    since_days: int = 7,
    recent_limit: int = 30,
) -> dict[str, Any]:
    """Return a grouped, read-only board view for one family group.

    Board data is aggregated from the existing ``memories`` table by kind.
    Nothing here performs writes; it is safe to expose to the board UI.

    Returns a dict with:
      - ``group``: the requested group id
      - ``generated_at``: ISO timestamp of the snapshot
      - ``recent``: most recent memories (newest first)
      - ``by_kind``: per-kind lists (event, expense, task, note)
    """
    today = today or datetime.now(timezone.utc)
    rows = store.list_memories(group_id, limit=recent_limit)
    by_kind: dict[str, list[dict[str, Any]]] = {k: [] for k in ALLOWED_KINDS}
    for row in rows:
        entry = {key: row[key] for key in row.keys()}
        by_kind.setdefault(entry.get("kind", "note"), []).append(entry)
    return {
        "group": group_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recent": [_serialize_row(r) for r in rows],
        "by_kind": {
            kind: [_serialize_row(r) for r in entries]
            for kind, entries in by_kind.items()
        },
    }


def _serialize_row(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}