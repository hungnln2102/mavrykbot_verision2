"""
Handler tin nhắn text: nhận "thông tin đơn hàng|slot|note" → lấy NCC → gửi bàn phím.
Mọi reply luôn gửi vào topic New Order (order_done_thread_id hoặc NEW_ORDER_TOPIC_ID).
"""
from __future__ import annotations

import asyncio
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from mavrykbot.handlers.new_order.api import get_suppliers
from mavrykbot.handlers.new_order.utils import reply_in_topic_kw

logger = logging.getLogger(__name__)


async def order_done_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nhận tin nhắn text khi đang chờ nhập 'thông tin đơn hàng|slot|note' cho luồng Hoàn thành."""
    if not update.message or not update.message.text:
        return
    order_id = context.user_data.get("order_done_id")
    if not order_id:
        return
    text = (update.message.text or "").strip()
    parts = text.split("|", 2)
    info = parts[0].strip() if len(parts) > 0 else ""
    slot = parts[1].strip() if len(parts) > 1 else ""
    note = parts[2].strip() if len(parts) > 2 else ""
    context.user_data["order_done_info"] = info
    context.user_data["order_done_slot"] = slot
    context.user_data["order_done_note"] = note

    loop = asyncio.get_event_loop()
    ok, suppliers, err = await loop.run_in_executor(None, get_suppliers)
    if not ok or not suppliers:
        thread_id = context.user_data.get("order_done_thread_id")
        reply_kw = reply_in_topic_kw(thread_id)
        err_msg = err or "trống"
        logger.error("get_suppliers failed: ok=%s suppliers_count=0 err=%s", ok, err_msg)
        print(f"[MAVRYKBOT] get_suppliers failed: {err_msg}", file=sys.stderr, flush=True)
        await update.effective_chat.send_message(
            f"Không lấy được danh sách NCC: {err_msg}. Thử lại sau.",
            **reply_kw,
        )
        return

    keyboard = []
    buttons_row = []
    for s in suppliers:
        sid = s.get("id") or s.get("supplier_name", "")
        name = s.get("supplier_name") or str(sid)
        buttons_row.append(InlineKeyboardButton(name, callback_data=f"done_supply:{sid}"))
        if len(buttons_row) == 3:
            keyboard.append(buttons_row)
            buttons_row = []
    if buttons_row:
        keyboard.append(buttons_row)
    keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="done_cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    thread_id = context.user_data.get("order_done_thread_id")
    reply_kw = reply_in_topic_kw(thread_id)
    await update.effective_chat.send_message(
        "Chọn NCC:",
        reply_markup=reply_markup,
        **reply_kw,
    )
