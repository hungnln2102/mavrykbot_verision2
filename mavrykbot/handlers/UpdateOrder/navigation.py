"""Navigation and display handlers for update order."""
import asyncio
import logging
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from mavrykbot.core.utils import escape_mdv2
from mavrykbot.handlers.menu import show_main_selector
from mavrykbot.handlers.UpdateOrder.models import OrderRecord
from mavrykbot.handlers.UpdateOrder.queries import query_orders_by_id, query_orders_by_info
from mavrykbot.handlers.UpdateOrder.states import INPUT_VALUE, SELECT_ACTION, SELECT_MODE
from mavrykbot.handlers.UpdateOrder.utils import (
    _delete_prompt_message,
    _edit_or_send_main_message,
    _format_order_message,
)

logger = logging.getLogger(__name__)


async def start_update_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Mã Đơn", callback_data="mode_id"),
            InlineKeyboardButton("Thông Tin Sản Phẩm", callback_data="mode_info"),
        ],
        [InlineKeyboardButton("Hủy", callback_data="cancel_update")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Vui lòng chọn chế độ tìm kiếm:"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, reply_markup=reply_markup
        )
        context.user_data["main_message_id"] = update.callback_query.message.message_id
    else:
        msg = await update.message.reply_text(message_text, reply_markup=reply_markup)
        context.user_data["main_message_id"] = msg.message_id
    return SELECT_MODE


async def select_check_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["check_mode"] = query.data
    prompt = (
        "Vui lòng nhập *Mã Đơn Hàng*:"
        if query.data == "mode_id"
        else "Vui Lòng Nhập *Thông Tin Sản Phẩm* Cần Tìm:"
    )
    await query.edit_message_text(
        prompt,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Hủy", callback_data="cancel_update")]]
        ),
    )
    return INPUT_VALUE


async def input_value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    search_term = (update.message.text or "").strip()
    await update.message.delete()

    chat_id = update.effective_chat.id
    check_mode = context.user_data.get("check_mode")

    await _edit_or_send_main_message(
        context,
        chat_id,
        "Đang tìm kiếm...",
        reply_markup=None,
    )

    try:
        if check_mode == "mode_id":
            matched = query_orders_by_id(search_term)
        else:
            matched = query_orders_by_info(search_term)
    except Exception as exc:
        logger.error("SQL search failed: %s", exc, exc_info=True)
        await _edit_or_send_main_message(
            context,
            chat_id,
            "Không thể tìm đơn hàng (lỗi DB).",
        )
        return await end_update(update, context)

    if not matched:
        await _edit_or_send_main_message(
            context,
            chat_id,
            "Không tìm thấy đơn hàng phù hợp.",
        )
        return await end_update(update, context)

    context.user_data["matched_orders"] = matched
    context.user_data["current_match_index"] = 0
    return await show_matched_order(update, context)


async def show_matched_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    direction: str = "stay",
    success_notice: Optional[str] = None,
) -> int:
    query = update.callback_query
    if query and not getattr(query, "answered", False):
        await query.answer()

    matched_orders: List[OrderRecord] = context.user_data.get("matched_orders", [])
    if not matched_orders:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Không có đơn hàng nào."
        )
        return await end_update(update, context)

    index = context.user_data.get("current_match_index", 0)
    if direction == "next":
        index += 1
    elif direction == "prev":
        index -= 1
    index = min(max(index, 0), len(matched_orders) - 1)
    context.user_data["current_match_index"] = index

    order = matched_orders[index]
    message_text = _format_order_message(order)
    if success_notice:
        message_text = f"_{escape_mdv2(success_notice)}_\n\n{message_text}"

    buttons: List[List[InlineKeyboardButton]] = []
    nav_row: List[InlineKeyboardButton] = []
    if len(matched_orders) > 1:
        if index > 0:
            nav_row.append(InlineKeyboardButton("Quay lại", callback_data="nav_prev"))
        if index < len(matched_orders) - 1:
            nav_row.append(InlineKeyboardButton("Tiếp", callback_data="nav_next"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton("Gia hạn", callback_data=f"action_extend|{order.ma_don}"),
            InlineKeyboardButton("Xóa", callback_data=f"action_delete|{order.ma_don}"),
            InlineKeyboardButton("Sửa", callback_data=f"action_edit|{order.ma_don}"),
        ]
    )
    buttons.append(
        [InlineKeyboardButton("Hủy & về menu", callback_data="cancel_update")]
    )

    if len(matched_orders) > 1:
        message_text += f"\n\nKết quả ({index + 1}/{len(matched_orders)})"

    await _edit_or_send_main_message(
        context,
        update.effective_chat.id,
        message_text,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_ACTION


async def end_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await asyncio.sleep(1)
    await _delete_prompt_message(context, context.bot)
    main_message_id = context.user_data.get("main_message_id")
    try:
        if update.callback_query:
            await show_main_selector(update, context, edit=True)
        else:
            if main_message_id:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=main_message_id
                )
            await show_main_selector(update, context, edit=False)
    except Exception as exc:
        logger.warning("Không thể quay lại menu: %s", exc)
        await show_main_selector(update, context, edit=False)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer("Đã Hủy")
    return await end_update(update, context)
