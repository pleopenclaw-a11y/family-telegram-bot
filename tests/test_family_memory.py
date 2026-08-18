import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import family_memory
from family_memory import add_memory, delete_memory, find_delete_candidates, search_memories
from telegram_bot import delete_term


class FamilyMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.sqlite3"
        self.patch = patch.object(family_memory, "DB_PATH", self.db)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_insert_and_search_is_group_scoped(self):
        add_memory("group-a", "นัดหมอพรุ่งนี้ 10 โมง", kind="event")
        add_memory("group-b", "นัดหมอพรุ่งนี้ 10 โมง", kind="event")
        self.assertEqual(len(search_memories("group-a", "นัดหมอ")), 1)
        self.assertEqual(len(search_memories("group-c", "นัดหมอ")), 0)

    def test_delete_removes_only_matching_group_record(self):
        first = add_memory("group-a", "ค่าอาหารแมว 450 บาท", kind="expense")
        second = add_memory("group-b", "ค่าอาหารแมว 450 บาท", kind="expense")
        self.assertTrue(delete_memory(first, "group-a"))
        self.assertEqual(len(search_memories("group-a", "อาหารแมว")), 0)
        self.assertEqual(len(search_memories("group-b", "อาหารแมว")), 1)
        self.assertFalse(delete_memory(second, "group-a"))

    def test_find_candidates_can_detect_ambiguous_delete(self):
        add_memory("group-a", "นัดหมอฟัน", kind="event")
        add_memory("group-a", "นัดหมอทั่วไป", kind="event")
        self.assertEqual(len(find_delete_candidates("group-a", "นัดหมอ")), 2)


class DeleteCommandParsingTests(unittest.TestCase):
    def test_natural_delete_terms(self):
        self.assertEqual(delete_term("ลบนัดหมอ"), "นัดหมอ")
        self.assertEqual(delete_term("ยกเลิก ค่าอาหาร"), "ค่าอาหาร")
        self.assertEqual(delete_term("delete appointment"), "appointment")

    def test_normal_message_is_not_delete(self):
        self.assertIsNone(delete_term("พรุ่งนี้มีนัดหมอ"))
        self.assertIsNone(delete_term("ลบ"))


if __name__ == "__main__":
    unittest.main()
