"""Track A tests: typed domain + SQLite storage foundation for the Family Board."""

from __future__ import annotations

import pytest

from domain import Event, Note, ShoppingItem, Task
from sqlite_store import SQLiteFamilyStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "board.sqlite3"
    s = SQLiteFamilyStore(db_path=db)
    yield s
    s.close()


# ---- Notes ---------------------------------------------------------------

def test_note_create_and_get_group_scoped(store):
    nid = store.create_note("group-a", Note(title="รับแพ็กเกจ", body="พัสดุจาก Lazada ถึงวันพฤหัส"))
    got = store.get_note("group-a", nid)
    assert got is not None
    assert got.title == "รับแพ็กเกจ"
    assert got.body == "พัสดุจาก Lazada ถึงวันพฤหัส"
    # other group cannot see it
    assert store.get_note("group-b", nid) is None


def test_note_list_orders_by_created_desc(store):
    a = store.create_note("g", Note(title="หนึ่ง", body="1"))
    b = store.create_note("g", Note(title="สอง", body="2"))
    notes = store.list_notes("g")
    assert [n.id for n in notes] == [b, a]


def test_note_delete(store):
    nid = store.create_note("g", Note(title="x", body="y"))
    assert store.delete_note("g", nid) is True
    assert store.get_note("g", nid) is None
    # cannot delete another group's note
    assert store.delete_note("g2", nid) is False


# ---- Events --------------------------------------------------------------

def test_event_create_with_datetime(store):
    eid = store.create_event("g", Event(title="ไปหาหมอ", at="2026-08-20T10:00:00+07:00"))
    ev = store.get_event("g", eid)
    assert ev is not None
    assert ev.title == "ไปหาหมอ"
    assert ev.at == "2026-08-20T10:00:00+07:00"


def test_event_upcoming_filter(store):
    store.create_event("g", Event(title="อดีต", at="2020-01-01T00:00:00+00:00"))
    future = store.create_event("g", Event(title="อนาคต", at="2099-01-01T00:00:00+00:00"))
    upcoming = store.list_events("g", upcoming_only=True)
    assert [e.id for e in upcoming] == [future]


# ---- Tasks ---------------------------------------------------------------

def test_task_toggle_done(store):
    tid = store.create_task("g", Task(title="จ่ายบิลค่าน้ำ"))
    assert store.get_task("g", tid).done is False
    store.set_task_done("g", tid, True)
    assert store.get_task("g", tid).done is True


def test_task_list_open_only(store):
    done = store.create_task("g", Task(title="ซื้อของเสร็จแล้ว", done=True))
    open_task = store.create_task("g", Task(title="ยังไม่เสร็จ"))
    tasks = store.list_tasks("g", open_only=True)
    assert [t.id for t in tasks] == [open_task]
    assert done not in [t.id for t in tasks]


# ---- Shopping ------------------------------------------------------------

def test_shopping_create_and_get(store):
    sid = store.create_shopping_item("g", ShoppingItem(name="นม", qty=2, purchased=False))
    item = store.get_shopping_item("g", sid)
    assert item is not None
    assert item.name == "นม"
    assert item.qty == 2
    assert item.purchased is False


def test_shopping_purchase_and_open_filter(store):
    bought = store.create_shopping_item("g", ShoppingItem(name="ไข่", qty=10, purchased=True))
    open_item = store.create_shopping_item("g", ShoppingItem(name="ข้าวสาร", qty=1))
    items = store.list_shopping("g", open_only=True)
    assert [i.id for i in items] == [open_item]
    assert bought not in [i.id for i in items]


def test_shopping_mark_purchased(store):
    sid = store.create_shopping_item("g", ShoppingItem(name="ผงซักฟอก", qty=1))
    store.set_shopping_purchased("g", sid, True)
    assert store.get_shopping_item("g", sid).purchased is True


# ---- Legacy compatibility ------------------------------------------------

def test_legacy_search_sees_board_notes(store):
    """Notes written through the board must be searchable via legacy family_memory."""
    store.create_note("g", Note(title="จด", body="นัดประชุมผู้ปกครอง"))
    hits = store.legacy_search("g", "ประชุม")
    texts = [h["text"] for h in hits]
    assert any("ประชุม" in t for t in texts)


def test_legacy_add_memory_round_trips_to_board(store):
    """Records written via legacy API surface in the board's note listing."""
    nid = store.legacy_add("g", "จำที่จะจ่ายค่าน้ำ", kind="note")
    notes = store.list_notes("g")
    assert any(n.legacy_id == nid for n in notes)


def test_legacy_delete_removes_board_note(store):
    nid = store.create_note("g", Note(title="ลบทิ้ง", body="เนื้อหาจะถูกลบ"))
    ok = store.legacy_delete(nid, "g")
    assert ok is True
    assert store.list_notes("g") == []