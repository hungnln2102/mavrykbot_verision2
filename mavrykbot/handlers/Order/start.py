import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from mavrykbot.core.utils import generate_unique_id

from .states import STATE_CHON_LOAI_KHACH, STATE_NHAP_TEN_SP
from .utils import safe_edit_md, md
from .finalize import end_add

logger = logging.getLogger(__name__)


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['main_message_id'] = query.message.message_id

    keyboard = [
        [
            InlineKeyboardButton("Khách Lẻ", callback_data="le"),
            InlineKeyboardButton("Cộng Tác Viên", callback_data="ctv"),
        ],
        [
            InlineKeyboardButton("Khuyến Mãi", callback_data="mavk"),
        ],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")],
    ]

    chat_id = query.message.chat.id
    await safe_edit_md(
        context.bot, chat_id, query.message.message_id,
        text="📦 *Khởi Tạo Đơn Hàng Mới*\n\nVui lòng lựa chọn phân loại khách hàng:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_LOAI_KHACH


async def chon_loai_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["loai_khach"] = query.data
    chat_id = query.message.chat.id

    try:
        ma_don = generate_unique_id(query.data) 
        context.user_data["ma_don"] = ma_don
    except Exception as e:
        logger.error(f"Lỗi tạo mã đơn: {e}")
        await safe_edit_md(context.bot, chat_id, query.message.message_id, md("❌ Lỗi tạo mã đơn."))
        return await end_add(update, context, success=False)

    text = f"🧾 Mã đơn: `{md(ma_don)}`\n\n🏷️ Vui lòng nhập *Tên Sản Phẩm*:"
    await safe_edit_md(
        context.bot, chat_id, query.message.message_id,
        text=text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_TEN_SP
