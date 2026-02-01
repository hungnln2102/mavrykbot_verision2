"""Edit field handlers for update order."""
import logging
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import ORDER_LIST_TABLE, OrderListColumns
from mavrykbot.core.utils import chuan_hoa_gia
from mavrykbot.handlers.UpdateOrder.models import FIELD_CONFIG, FIELD_MENU_LAYOUT, OrderRecord
from mavrykbot.handlers.UpdateOrder.queries import check_source_exists
from mavrykbot.handlers.UpdateOrder.states import (
    EDIT_CHOOSE_FIELD,
    EDIT_INPUT_LINK_KHACH,
    EDIT_INPUT_NGUON,
    EDIT_INPUT_SIMPLE,
    EDIT_INPUT_SO_NGAY,
    EDIT_INPUT_TEN_KHACH,
)
from mavrykbot.handlers.UpdateOrder.utils import (
    _get_active_order,
    _store_prompt_message,
    _update_prompt_message,
)

logger = logging.getLogger(__name__)


def _persist_field_change(order: OrderRecord, field_key: str, value):
    cfg = FIELD_CONFIG[field_key]
    column = cfg["column"]
    db.execute(
        f"UPDATE {ORDER_LIST_TABLE} SET {column} = %s WHERE {OrderListColumns.ID} = %s",
        (value, order.db_id),
    )
    setattr(order, cfg["attr"], value)


async def _finalize_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    field_key: Optional[str] = None,
    value,
    success_notice: Optional[str] = None,
) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import show_matched_order
    
    if field_key is None:
        field_key = context.user_data.get("edit_field")
    if not field_key:
        await update.message.reply_text("Không xác định trường cần cập nhật.")
        return EDIT_INPUT_SIMPLE
    try:
        order = _get_active_order(context)
        _persist_field_change(order, field_key, value)
    except Exception as exc:
        logger.error("Cập nhật trường %s thất bại: %s", field_key, exc, exc_info=True)
        await update.message.reply_text("Không thể cập nhật DB.")
        return FIELD_CONFIG[field_key]["state"]
    if update.message:
        await update.message.delete()
    notice = success_notice or f"Đã cập nhật {FIELD_CONFIG[field_key]['label']}."
    return await show_matched_order(update, context, success_notice=notice)


async def start_edit_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ma_don = query.data.split("|", 1)[1].strip()
    context.user_data["edit_ma_don"] = ma_don
    keyboard: List[List[InlineKeyboardButton]] = []
    for row in FIELD_MENU_LAYOUT:
        buttons: List[InlineKeyboardButton] = []
        for field_key in row:
            if not field_key:
                continue
            cfg = FIELD_CONFIG[field_key]
            buttons.append(
                InlineKeyboardButton(
                    str(cfg["label"]),
                    callback_data=f"edit|{field_key}"
                )
            )
        if buttons:
            keyboard.append(buttons)
    keyboard.append([InlineKeyboardButton("Quay Lại", callback_data="back_to_order")])
    await query.edit_message_text(
        "Chọn trường muốn chỉnh sửa:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_CHOOSE_FIELD


async def choose_field_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import end_update
    
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|", 1)
    if len(parts) < 2 or parts[1] not in FIELD_CONFIG:
        await query.edit_message_text("Trường không hợp lệ.")
        return await end_update(update, context)

    field_key = parts[1]
    context.user_data["edit_field"] = field_key
    cfg = FIELD_CONFIG[field_key]

    keyboard = [[InlineKeyboardButton("Hủy", callback_data="cancel_update")]]
    if field_key == "LINK_KHACH":
        keyboard.insert(0, [InlineKeyboardButton("Bỏ trống", callback_data="skip_link_khach")])
    
    _store_prompt_message(context, query.message.chat.id, query.message.message_id)
    
    await query.edit_message_text(
        f"Nhập giá trị mới cho *{cfg['label']}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return cfg["state"]


async def back_to_order_display(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import show_matched_order
    return await show_matched_order(update, context)


async def input_new_simple_value_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    field_key = context.user_data.get("edit_field")
    text = (update.message.text or "").strip()
    if not field_key:
        await update.message.reply_text("Không xác định trường cần cập nhật.")
        return EDIT_INPUT_SIMPLE
    if field_key in {"GIA_NHAP", "GIA_BAN"}:
        _, number = chuan_hoa_gia(text)
        value = number
    else:
        if not text:
            await update.message.reply_text("Giá trị không được để trống.")
            return FIELD_CONFIG[field_key]["state"]
        value = text
    return await _finalize_edit(update, context, field_key=field_key, value=value)


async def input_new_nguon_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Nhập tên nguồn hợp lệ.")
        return EDIT_INPUT_NGUON
    try:
        exists = check_source_exists(text)
    except Exception as exc:
        logger.error("Tìm nguồn lỗi: %s", exc, exc_info=True)
        await update.message.reply_text("Không thể kiểm tra nguồn.")
        return EDIT_INPUT_NGUON
    if not exists:
        await update.message.reply_text("Nguồn không tồn tại.")
        return EDIT_INPUT_NGUON
    return await _finalize_edit(update, context, field_key="NGUON", value=text)


async def input_new_so_ngay_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    try:
        value = int(text)
    except ValueError:
        await update.message.reply_text("Vui lòng nhập số nguyên.")
        return EDIT_INPUT_SO_NGAY
    if value <= 0:
        await update.message.reply_text("Số ngày phải > 0.")
        return EDIT_INPUT_SO_NGAY
    return await _finalize_edit(update, context, field_key="SO_NGAY", value=value)


async def input_new_ten_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Ten khach khong duoc rong.")
        return EDIT_INPUT_TEN_KHACH

    try:
        order = _get_active_order(context)
        _persist_field_change(order, "TEN_KHACH", text)
    except Exception as exc:
        logger.error("Cap nhat ten khach that bai: %s", exc, exc_info=True)
        await update.message.reply_text("Khong the cap nhat ten khach.")
        return EDIT_INPUT_TEN_KHACH

    if update.message:
        await update.message.delete()

    context.user_data["after_name_link"] = True
    context.user_data["edit_field"] = "LINK_KHACH"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Bỏ qua", callback_data="skip_link_after_name")],
        [InlineKeyboardButton("Hủy", callback_data="cancel_update")],
    ])
    prompt_text = "Nhập thông tin liên hệ khách hàng (hoặc Bỏ qua):"
    await _update_prompt_message(context, prompt_text, reply_markup=keyboard)
    return EDIT_INPUT_LINK_KHACH


async def input_new_link_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    after_name = context.user_data.pop("after_name_link", False)
    success = "Da cap nhat ten khach & lien he." if after_name else None
    context.user_data["edit_field"] = "LINK_KHACH"
    return await _finalize_edit(
        update, context, field_key="LINK_KHACH", value=text, success_notice=success
    )


async def skip_link_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    return await _finalize_edit(
        update, context, field_key="LINK_KHACH", value="", success_notice="Đã Bỏ Qua Liên Hệ."
    )


async def skip_link_after_name_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import show_matched_order
    
    query = update.callback_query
    await query.answer("Bo qua lien he.")
    context.user_data.pop("after_name_link", None)
    context.user_data.pop("edit_field", None)
    return await show_matched_order(update, context, success_notice="Đã Cập Nhật Tên Khách")
