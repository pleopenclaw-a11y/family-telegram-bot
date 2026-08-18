import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from board_service import PreviewResult
import telegram_bot


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.chat_id = 123
        self.message_id = 456
        self.chat = SimpleNamespace(id=self.chat_id)
        self.from_user = SimpleNamespace(id=789, full_name="แม่")
        self.reply_text = AsyncMock()


class TelegramConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def context(self, text):
        return SimpleNamespace(
            bot=SimpleNamespace(send_chat_action=AsyncMock()),
            chat_data={},
        ), FakeMessage(text)

    async def test_save_preview_is_pending_until_yes(self):
        context, message = self.context("ซื้อของเข้าบ้าน")
        preview = PreviewResult(
            text=message.text, action="save", kind="task",
            normalized_text="ซื้อของเข้าบ้าน", confidence=0.95, question="",
        )
        with patch.object(telegram_bot, "preview_capture", return_value=preview) as preview_capture, \
             patch.object(telegram_bot, "commit_capture") as commit:
            await telegram_bot.chat(SimpleNamespace(message=message, effective_chat=message.chat), context)

            preview_capture.assert_called_once()
            commit.assert_not_called()
            self.assertIs(context.chat_data[telegram_bot.PENDING_CAPTURE_KEY].preview, preview)
            self.assertIn("ใช่", message.reply_text.await_args.args[0])

            message.text = "ใช่"
            message.message_id = 999
            message.from_user = SimpleNamespace(id=999, full_name="พ่อ")
            await telegram_bot.chat(SimpleNamespace(message=message, effective_chat=message.chat), context)

        commit.assert_called_once_with(
            "123", kind="task", normalized_text="ซื้อของเข้าบ้าน",
            user_id="789", user_name="แม่", source_message_id=456,
        )
        self.assertNotIn(telegram_bot.PENDING_CAPTURE_KEY, context.chat_data)

    async def test_no_cancels_pending_preview_without_committing(self):
        context, message = self.context("จ่ายค่าน้ำ")
        context.chat_data[telegram_bot.PENDING_CAPTURE_KEY] = telegram_bot.PendingCapture(
            preview=PreviewResult(
                text=message.text, action="save", kind="expense",
                normalized_text="จ่ายค่าน้ำ", confidence=0.9, question="",
            ),
            user_id="789", user_name="แม่", source_message_id=456,
        )
        with patch.object(telegram_bot, "commit_capture") as commit:
            message.text = "ไม่"
            await telegram_bot.chat(SimpleNamespace(message=message, effective_chat=message.chat), context)

        commit.assert_not_called()
        self.assertNotIn(telegram_bot.PENDING_CAPTURE_KEY, context.chat_data)
        self.assertIn("ยกเลิก", message.reply_text.await_args.args[0])

    async def test_invalid_confirmation_keeps_pending_and_does_not_reclassify(self):
        context, message = self.context("ซื้อไข่")
        pending = PreviewResult(
            text=message.text, action="save", kind="task",
            normalized_text="ซื้อไข่", confidence=0.9, question="",
        )
        context.chat_data[telegram_bot.PENDING_CAPTURE_KEY] = telegram_bot.PendingCapture(
            preview=pending, user_id="789", user_name="แม่", source_message_id=456,
        )
        with patch.object(telegram_bot, "preview_capture") as preview_capture, \
             patch.object(telegram_bot, "commit_capture") as commit:
            message.text = "อาจจะ"
            await telegram_bot.chat(SimpleNamespace(message=message, effective_chat=message.chat), context)

        preview_capture.assert_not_called()
        commit.assert_not_called()
        self.assertIs(context.chat_data[telegram_bot.PENDING_CAPTURE_KEY].preview, pending)
        self.assertIn("ใช่", message.reply_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
