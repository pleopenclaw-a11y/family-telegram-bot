from __future__ import annotations

import asyncio
import html
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import load_settings
from family_memory import delete_memory, find_delete_candidates, list_memories, search_memories, utc_days_ago
from board_service import PreviewResult, commit_capture, preview_capture
from ninearm_client import NineArmClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = load_settings()
client = NineArmClient(settings.ninearm_base_url, settings.ninearm_api_key, settings.primary_model, settings.fallback_model)

COMMANDS = [
    BotCommand("start", "เริ่มใช้งานบอท"), BotCommand("help", "ดูคำสั่งทั้งหมด"),
    BotCommand("today", "ดูรายการวันนี้"), BotCommand("week", "ดูรายการสัปดาห์นี้"),
    BotCommand("expenses", "ดูค่าใช้จ่าย"), BotCommand("search", "ค้นหาข้อมูล"),
    BotCommand("delete", "ลบรายการที่บันทึก"),
]
PENDING_CAPTURE_KEY = "pending_capture"
YES_WORDS = {"yes", "y", "ใช่", "ตกลง", "บันทึก"}
NO_WORDS = {"no", "n", "ไม่", "ยกเลิก", "cancel"}


@dataclass(frozen=True)
class PendingCapture:
    preview: PreviewResult
    user_id: str | None
    user_name: str | None
    source_message_id: int | None


def code_block(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


def group_id(update: Update) -> str:
    return str(update.effective_chat.id)


def format_rows(title: str, rows) -> str:
    lines = [title, ""]
    if not rows:
        lines.append("ยังไม่มีข้อมูลค่ะ")
    else:
        for row in rows:
            who = row["user_name"] or row["user_id"] or "ไม่ทราบชื่อ"
            lines.append(f"[{row['kind']}] {row['text']}")
            lines.append(f"โดย: {who} | {row['created_at'][:16].replace('T', ' ')} UTC")
            lines.append("")
    return "\n".join(lines)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(COMMANDS)
    logging.info("Telegram slash commands registered")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("สวัสดีค่ะ Family Bot พร้อมใช้งานแล้ว\nข้อมูลข้อความในกลุ่มจะถูกเก็บเป็น Family Memory ค่ะ")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = """คำสั่ง Family Bot

/start     เริ่มใช้งาน
/help      ดูคำสั่งทั้งหมด
/today     ดูรายการวันนี้
/week      ดูรายการสัปดาห์นี้
/expenses  ดูค่าใช้จ่าย
/search    ค้นหาข้อมูล เช่น /search ประกันรถ

พิมพ์ข้อความธรรมชาติในกลุ่มได้เลยค่ะ ระบบจะเก็บเป็น memory"""
    await update.message.reply_text(code_block(text), parse_mode=ParseMode.HTML)


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = list_memories(group_id(update), since=utc_days_ago(1))
    await update.message.reply_text(code_block(format_rows("Family Memory — วันนี้", rows)), parse_mode=ParseMode.HTML)


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = list_memories(group_id(update), since=utc_days_ago(7))
    await update.message.reply_text(code_block(format_rows("Family Memory — 7 วันที่ผ่านมา", rows)), parse_mode=ParseMode.HTML)


async def expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = list_memories(group_id(update), kind="expense", limit=50)
    await update.message.reply_text(code_block(format_rows("Family Memory — ค่าใช้จ่าย", rows)), parse_mode=ParseMode.HTML)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    term = " ".join(context.args).strip()
    if not term:
        await update.message.reply_text(code_block("รูปแบบการใช้:\n/search คำค้น"), parse_mode=ParseMode.HTML)
        return
    rows = search_memories(group_id(update), term)
    await update.message.reply_text(code_block(format_rows(f"ผลการค้นหา: {term}", rows)), parse_mode=ParseMode.HTML)


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    term = " ".join(context.args).strip()
    if not term:
        await update.message.reply_text(code_block("รูปแบบการใช้:\n/delete คำค้น\n\nตัวอย่าง:\n/delete นัดหมอ"), parse_mode=ParseMode.HTML)
        return
    rows = find_delete_candidates(group_id(update), term)
    if len(rows) == 1:
        row = rows[0]
        deleted = delete_memory(int(row["id"]), group_id(update))
        status = "ลบรายการแล้วค่ะ" if deleted else "ไม่พบรายการที่ต้องการลบค่ะ"
        await update.message.reply_text(code_block(f"{status}\n[{row['kind']}] {row['text']}"), parse_mode=ParseMode.HTML)
    elif not rows:
        await update.message.reply_text(code_block("ไม่พบรายการที่ตรงกับคำค้นค่ะ"), parse_mode=ParseMode.HTML)
    else:
        lines = ["พบหลายรายการ กรุณาใช้คำค้นให้ละเอียดขึ้นค่ะ", ""]
        lines.extend(f"ID {r['id']}: [{r['kind']}] {r['text']}" for r in rows)
        await update.message.reply_text(code_block("\n".join(lines)), parse_mode=ParseMode.HTML)


def delete_term(text: str) -> str | None:
    match = re.match(r"^\s*(?:ลบ|ยกเลิก|delete)\s*(.+)$", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def confirmation_answer(text: str) -> str | None:
    answer = text.strip().casefold()
    if answer in YES_WORDS:
        return "yes"
    if answer in NO_WORDS:
        return "no"
    return None


async def handle_pending_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    pending = context.chat_data.get(PENDING_CAPTURE_KEY)
    if not pending:
        return False
    message = update.message
    answer = confirmation_answer(message.text)
    if answer == "yes":
        context.chat_data.pop(PENDING_CAPTURE_KEY, None)
        preview = pending.preview
        commit_capture(
            group_id(update), kind=preview.kind, normalized_text=preview.normalized_text,
            user_id=pending.user_id, user_name=pending.user_name,
            source_message_id=pending.source_message_id,
        )
        await message.reply_text(code_block("บันทึกแล้วค่ะ"), parse_mode=ParseMode.HTML)
    elif answer == "no":
        context.chat_data.pop(PENDING_CAPTURE_KEY, None)
        await message.reply_text(code_block("ยกเลิกการบันทึกแล้วค่ะ"), parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(code_block("กรุณาตอบ ใช่ เพื่อบันทึก หรือ ไม่ เพื่อยกเลิกค่ะ"), parse_mode=ParseMode.HTML)
    return True


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    message = update.message
    text = message.text.strip()
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    if await handle_pending_capture(update, context):
        return
    if term := delete_term(text):
        rows = find_delete_candidates(group_id(update), term)
        if len(rows) == 1:
            row = rows[0]
            delete_memory(int(row["id"]), group_id(update))
            await message.reply_text(code_block(f"ลบรายการแล้วค่ะ\n[{row['kind']}] {row['text']}"), parse_mode=ParseMode.HTML)
        elif rows:
            lines = ["พบหลายรายการ กรุณาระบุคำค้นให้ละเอียดขึ้นค่ะ", ""]
            lines.extend(f"ID {r['id']}: [{r['kind']}] {r['text']}" for r in rows)
            await message.reply_text(code_block("\n".join(lines)), parse_mode=ParseMode.HTML)
        else:
            await message.reply_text(code_block("ไม่พบรายการที่ตรงกับคำขอลบค่ะ"), parse_mode=ParseMode.HTML)
        return
    try:
        extraction = await asyncio.wait_for(
            asyncio.to_thread(preview_capture, client, text), timeout=95
        )
        if extraction.action == "ignore":
            return
        if extraction.action == "confirm":
            question = extraction.question or "ข้อความนี้มีข้อมูลที่ควรบันทึกใน Family Memory ใช่ไหมคะ?"
            await message.reply_text(code_block(question), parse_mode=ParseMode.HTML)
            return
        user = message.from_user
        context.chat_data[PENDING_CAPTURE_KEY] = PendingCapture(
            preview=extraction,
            user_id=str(user.id) if user else None,
            user_name=user.full_name if user else None,
            source_message_id=message.message_id,
        )
        await message.reply_text(
            code_block(f"บันทึกข้อความนี้ไหมคะ?\n\n{extraction.normalized_text}\n\nตอบ ใช่ หรือ ไม่ค่ะ"),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logging.exception("message extraction or 9arm request failed")
        await message.reply_text(code_block("ยังไม่ได้บันทึกข้อความนี้ค่ะ เพราะ AI classifier ทำงานไม่สำเร็จ กรุณาลองใหม่อีกครั้ง"), parse_mode=ParseMode.HTML)


def main() -> None:
    if not settings.telegram_bot_token or settings.telegram_bot_token == "xxx": raise SystemExit("Set TELEGRAM_BOT_TOKEN")
    if not settings.ninearm_api_key or settings.ninearm_api_key == "xxx": raise SystemExit("Set NINEARM_API_KEY")
    app = Application.builder().token(settings.telegram_bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today)); app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("expenses", expenses)); app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    logging.info("Family Telegram Bot starting with long polling")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
