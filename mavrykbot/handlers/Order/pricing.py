import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .states import STATE_NHAP_GIA_BAN, STATE_NHAP_NOTE
from .utils import safe_edit_md, _parse_price, _round_thousand

logger = logging.getLogger(__name__)


async def nhap_gia_ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gia_ban_raw = update.message.text.strip()
    await update.message.delete()
    
    gia_ban_value = _parse_price(gia_ban_raw)

    if gia_ban_value < 0:
        await safe_edit_md(
            context.bot, update.effective_chat.id, context.user_data['main_message_id'],
            text="⚠️ Giá bán không hợp lệ. Vui lòng chỉ nhập số:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return STATE_NHAP_GIA_BAN

    gia_ban_rounded = _round_thousand(gia_ban_value)
    logger.info(f"LOG_PRICE_CALC | Manual price entered: {gia_ban_value}, Rounded to nearest thousand: {gia_ban_rounded}")

    context.user_data["gia_ban_value"] = gia_ban_rounded

    keyboard = [
        [InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_note")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]
    ]
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="📝 Vui lòng nhập *Ghi chú* \\(nếu có\\) hoặc bấm Bỏ Qua:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_NOTE
