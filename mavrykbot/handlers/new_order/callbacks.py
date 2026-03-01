"""
Callback handlers cho New Order: Hoàn thành, Hủy Đơn, chọn NCC, hủy luồng.
Mọi reply luôn gửi vào topic New Order (message_thread_id hoặc NEW_ORDER_TOPIC_ID).
"""
from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from mavrykbot.handlers.new_order.api import call_order_api
from mavrykbot.handlers.new_order.utils import reply_in_topic_kw, get_new_order_topic_id


async def handle_order_done(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str) -> None:
    """Bấm Hoàn thành: lưu thread_id (hoặc New Order topic từ env), nhắc nhập thông tin đơn|slot|note."""
    thread_id = getattr(update.callback_query.message, "message_thread_id", None)
    if thread_id is None:
        thread_id = get_new_order_topic_id()
    context.user_data["order_done_id"] = order_id
    context.user_data["order_done_thread_id"] = thread_id
    context.user_data.pop("order_done_info", None)
    context.user_data.pop("order_done_slot", None)
    context.user_data.pop("order_done_note", None)
    reply_kw = reply_in_topic_kw(thread_id)
    await update.effective_chat.send_message(
        f"📋 <b>Hoàn thành đơn {order_id}</b>\n\n"
        "Nhập theo format: <code>thông tin đơn hàng|slot|note</code>\n"
        "Ví dụ: <code>GPT Plus Add Team (1 tháng)|Slot1|Giao nhanh</code>\n"
        "Có thể để trống, ví dụ: <code>||</code> hoặc <code>Sản phẩm A||</code>",
        parse_mode="HTML",
        **reply_kw,
    )


async def handle_order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: str) -> None:
    """Bấm Hủy Đơn: gọi API cancel, reply trong topic New Order."""
    thread_id = getattr(update.callback_query.message, "message_thread_id", None)
    reply_kw = reply_in_topic_kw(thread_id)
    loop = asyncio.get_event_loop()
    ok, msg = await loop.run_in_executor(
        None,
        lambda: call_order_api("/api/orders/cancel", {"id_order": order_id}),
    )
    if ok:
        await update.effective_chat.send_message(f"✅ Đã hủy đơn: {order_id}", **reply_kw)
        try:
            await update.callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await update.effective_chat.send_message(f"❌ Hủy đơn thất bại: {msg}", **reply_kw)


async def handle_done_supply(update: Update, context: ContextTypes.DEFAULT_TYPE, supplier_id: str) -> None:
    """Chọn NCC: gọi notify-done, reply trong topic New Order."""
    order_id = context.user_data.pop("order_done_id", None)
    thread_id = context.user_data.pop("order_done_thread_id", None)
    info = context.user_data.pop("order_done_info", "")
    slot = context.user_data.pop("order_done_slot", "")
    note = context.user_data.pop("order_done_note", "")
    reply_kw = reply_in_topic_kw(thread_id)
    if not order_id:
        await update.effective_chat.send_message(
            "Phiên nhập đã hết. Bấm lại Hoàn thành từ tin nhắn đơn hàng.",
            **reply_kw,
        )
        return
    body = {
        "id_order": order_id,
        "information_order": info or None,
        "slot": slot or None,
        "note": note or None,
        "supply": supplier_id,
    }
    loop = asyncio.get_event_loop()
    ok, msg = await loop.run_in_executor(
        None,
        lambda: call_order_api("/api/orders/notify-done", body),
    )
    if ok:
        await update.effective_chat.send_message(
            f"✅ Đã cập nhật order_list: Mã đơn {order_id}, thông tin đơn hàng, slot, note, NCC đã ghi.",
            **reply_kw,
        )
    else:
        await update.effective_chat.send_message(f"❌ Gửi lên hệ thống thất bại: {msg}", **reply_kw)


async def handle_done_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hủy luồng Hoàn thành: xóa user_data, reply trong topic New Order."""
    thread_id = context.user_data.pop("order_done_thread_id", None)
    context.user_data.pop("order_done_id", None)
    context.user_data.pop("order_done_info", None)
    context.user_data.pop("order_done_slot", None)
    context.user_data.pop("order_done_note", None)
    reply_kw = reply_in_topic_kw(thread_id)
    await update.effective_chat.send_message("Đã hủy.", **reply_kw)


async def new_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Router: xử lý callback_data order_done:, order_cancel:, done_supply:, done_cancel.
    Chỉ được gọi khi filter khớp (từ __init__.py).
    """
    query = update.callback_query
    data = (query.data or "").strip()
    await query.answer()

    if data.startswith("order_done:"):
        order_id = data[len("order_done:"):].strip()
        if not order_id:
            reply_kw = reply_in_topic_kw(get_new_order_topic_id())
            await update.effective_chat.send_message("Mã đơn trống.", **reply_kw)
            return
        await handle_order_done(update, context, order_id)
        return

    if data.startswith("order_cancel:"):
        order_id = data[len("order_cancel:"):].strip()
        if not order_id:
            reply_kw = reply_in_topic_kw(get_new_order_topic_id())
            await update.effective_chat.send_message("Mã đơn trống.", **reply_kw)
            return
        await handle_order_cancel(update, context, order_id)
        return

    if data.startswith("done_supply:"):
        supplier_id = data[len("done_supply:"):].strip()
        await handle_done_supply(update, context, supplier_id)
        return

    if data == "done_cancel":
        await handle_done_cancel(update, context)
        return
