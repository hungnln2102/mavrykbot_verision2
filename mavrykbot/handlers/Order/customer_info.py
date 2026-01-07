from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .states import (
    STATE_NHAP_THONG_TIN,
    STATE_NHAP_TEN_KHACH,
    STATE_NHAP_LINK_KHACH,
    STATE_NHAP_SLOT,
    STATE_NHAP_GIA_BAN,
    STATE_NHAP_NOTE,
)
from .utils import safe_edit_md


async def nhap_thong_tin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["thong_tin_don"] = update.message.text.strip()
    await update.message.delete()
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="👤 Vui lòng nhập *tên khách hàng*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_TEN_KHACH


async def nhap_ten_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["khach_hang"] = update.message.text.strip()
    await update.message.delete()
    keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_link")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="🔗 Vui lòng nhập *thông tin liên hệ* hoặc bấm Bỏ Qua:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_LINK_KHACH


async def nhap_link_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, skip: bool = False) -> int:
    query = update.callback_query
    if skip:
        context.user_data["link_khach"] = ""
        await query.answer()
        chat_id = query.message.chat.id
        mid = query.message.message_id
    else:
        context.user_data["link_khach"] = update.message.text.strip()
        await update.message.delete()
        chat_id = update.effective_chat.id
        mid = context.user_data['main_message_id']
    keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_slot")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
    await safe_edit_md(
        context.bot, chat_id, mid,
        text="🧩 Vui lòng nhập *Slot* \\(nếu có\\) hoặc bấm Bỏ Qua:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_SLOT


async def nhap_slot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, skip: bool = False) -> int:
    query = update.callback_query
    if skip:
        context.user_data["slot"] = ""
        await query.answer()
        chat_id = query.message.chat.id
        mid = query.message.message_id
    else:
        context.user_data["slot"] = update.message.text.strip()
        await update.message.delete()
        chat_id = update.effective_chat.id
        mid = context.user_data['main_message_id']

    if "gia_ban_value" in context.user_data and context.user_data["gia_ban_value"] > 0:
        keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_note")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
        await safe_edit_md(
            context.bot, chat_id, mid,
            text="📝 Vui lòng nhập *Ghi chú* \\(nếu có\\) hoặc bấm Bỏ Qua:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STATE_NHAP_NOTE
    else:
        await safe_edit_md(
            context.bot, chat_id, mid,
            text="💵 Vui lòng nhập *Giá bán*:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return STATE_NHAP_GIA_BAN
