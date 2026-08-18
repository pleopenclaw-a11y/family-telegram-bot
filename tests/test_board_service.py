import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import board_service
import family_memory as store
from ninearm_client import NineArmClient


class BoardServiceTests(unittest.TestCase):
    """Confirmation-safe action protocol + board read boundary."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.sqlite3"
        self.patch = patch.object(store, "DB_PATH", self.db)
        self.patch.start()
        # A client with a placeholder key is fine: the extractor is faked below,
        # so no network/credential is ever used during tests.
        self.client = NineArmClient(
            base_url="https://gateway.example/v1",
            api_key="test-key-placeholder",
            primary_model="primary",
            fallback_model="fallback",
        )

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    # --- preview is side-effect free ------------------------------------

    def test_preview_capture_does_not_persist(self):
        class FakeExtract:
            def __call__(self, client, text):
                from extractor import Extraction
                return Extraction(
                    action="save",
                    kind="event",
                    normalized_text="นัดหมอพรุ่งนี้ 10 โมง",
                    confidence=0.95,
                    question="",
                )

        result = board_service.preview_capture(self.client, "พรุ่งนี้มีนัดหมอ 10 โมง", extract=FakeExtract())
        self.assertEqual(result.action, "save")
        self.assertEqual(result.kind, "event")
        self.assertEqual(result.normalized_text, "นัดหมอพรุ่งนี้ 10 โมง")
        self.assertEqual(result.confidence, 0.95)
        # No writes happened during preview.
        self.assertEqual(len(store.list_memories("group-a")), 0)

    def test_preview_confirm_action_surfaces_question(self):
        class FakeExtract:
            def __call__(self, client, text):
                from extractor import Extraction
                return Extraction(
                    action="confirm",
                    kind="task",
                    normalized_text="ล้างรถ",
                    confidence=0.4,
                    question="ต้องระบุวันล้างรถด้วยไหมคะ?",
                )

        result = board_service.preview_capture(self.client, "ล้างรถ", extract=FakeExtract())
        self.assertEqual(result.action, "confirm")
        self.assertIn("วันล้างรถ", result.question)
        self.assertEqual(len(store.list_memories("group-a")), 0)

    def test_preview_ignore_action(self):
        class FakeExtract:
            def __call__(self, client, text):
                from extractor import Extraction
                return Extraction(
                    action="ignore", kind="note", normalized_text=text,
                    confidence=0.9, question="",
                )

        result = board_service.preview_capture(self.client, "สวัสดีครับทุกคน", extract=FakeExtract())
        self.assertEqual(result.action, "ignore")

    # --- commit is the single, explicit write path -----------------------

    def test_confirm_capture_persists(self):
        commit = board_service.commit_capture(
            "group-a", kind="expense", normalized_text="ค่าอาหารแมว 450 บาท",
        )
        self.assertIsInstance(commit.id, int)
        rows = store.search_memories("group-a", "อาหารแมว")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "expense")
        self.assertEqual(rows[0]["text"], "ค่าอาหารแมว 450 บาท")

    def test_commit_preserves_shopping_kind(self):
        commit = board_service.commit_capture(
            "group-a", kind="shopping", normalized_text="นม 2 ลิตร",
        )

        self.assertEqual(commit.kind, "shopping")
        board = board_service.get_board("group-a")
        self.assertEqual(len(board["by_kind"]["shopping"]), 1)
        self.assertEqual(board["by_kind"]["shopping"][0]["kind"], "shopping")

    def test_commit_is_group_scoped_and_kind_validated(self):
        one = board_service.commit_capture("group-a", kind="task", normalized_text="ซักผ้า")
        # Invalid kind falls back to note.
        two = board_service.commit_capture("group-a", kind="bogus", normalized_text="ทดสอบ")
        self.assertEqual(store.delete_memory(one.id, "group-a"), True)
        # Cannot delete group-a's record from group-z.
        self.assertEqual(store.delete_memory(two.id, "group-z"), False)

    def test_commit_preserves_metadata(self):
        commit = board_service.commit_capture(
            "group-a", kind="event", normalized_text="นัดหมอ",
            user_id="123", user_name="แม่", source_message_id=77,
        )
        row = store.search_memories("group-a", "นัดหมอ")[0]
        self.assertEqual(row["user_id"], "123")
        self.assertEqual(row["user_name"], "แม่")
        self.assertEqual(row["source_message_id"], 77)

    # --- board reads ------------------------------------------------------

    def test_get_board_groups_by_kind(self):
        board_service.commit_capture("group-a", kind="event", normalized_text="นัดหมอวันเสาร์")
        board_service.commit_capture("group-a", kind="task", normalized_text="ซื้อของให้แม่")
        board_service.commit_capture("group-a", kind="note", normalized_text="เบอร์ช่าง 087-xxx")
        board = board_service.get_board("group-a")
        self.assertEqual(board["group"], "group-a")
        self.assertEqual(len(board["recent"]), 3)
        self.assertEqual(len(board["by_kind"]["event"]), 1)
        self.assertEqual(len(board["by_kind"]["task"]), 1)
        self.assertEqual(len(board["by_kind"]["note"]), 1)

    def test_get_board_is_group_scoped(self):
        board_service.commit_capture("group-a", kind="note", normalized_text="ของกลุ่มเอ")
        empty = board_service.get_board("group-z")
        self.assertEqual(empty["recent"], [])
        self.assertEqual(len(empty["by_kind"]["note"]), 0)


if __name__ == "__main__":
    unittest.main()
