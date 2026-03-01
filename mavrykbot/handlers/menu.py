from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram
import logging

logger = logging.getLogger(__name__)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị menu chính (một cấp duy nhất)."""
    keyboard = [
        [
            InlineKeyboardButton("👤 Đơn Chưa Thanh Toán", callback_data='unpaid_orders'),
            InlineKeyboardButton("🏬 Shop", callback_data='menu_shop'),
        ],
        [
            InlineKeyboardButton("💰 Tạo QR Thanh Toán", callback_data='create_qr'),
            InlineKeyboardButton("💰 Thanh Toán Nguồn", callback_data='payment_source'),
        ],
        [
            InlineKeyboardButton("💸 Hoàn Tiền", callback_data='start_refund'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "🔽 *Chọn phân hệ làm việc:*"
    query = update.callback_query
    try:
        if query:
            if query.message.text:
                await query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown',
                )
            else:
                await query.message.delete()
                await query.message.chat.send_message(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown',
                )
        elif update.message:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
            )
    except telegram.error.BadRequest as e:
        logger.error("show_menu BadRequest: %s", e)
        try:
            await update.effective_chat.send_message(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
            )
        except Exception as final_e:
            logger.critical("Không thể gửi menu: %s", final_e)
