"""Typed domain entities for the Family Board.

Track A: these are the canonical objects used by the storage layer and,
eventually, by the API (Track C) and Telegram integration (Track D).
They are intentionally plain dataclasses so they can cross process and
interface boundaries cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Note:
    title: str
    body: str
    id: Optional[int] = None
    legacy_id: Optional[int] = None  # id of the backing `memories` row
    created_at: Optional[str] = None


@dataclass
class Event:
    title: str
    at: str  # ISO-8601 datetime string
    id: Optional[int] = None
    legacy_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Task:
    title: str
    done: bool = False
    id: Optional[int] = None
    legacy_id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class ShoppingItem:
    name: str
    qty: int = 1
    purchased: bool = False
    id: Optional[int] = None
    legacy_id: Optional[int] = None
    created_at: Optional[str] = None