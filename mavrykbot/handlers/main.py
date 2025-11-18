"""
Điểm khởi chạy chính cho Bot Telegram.
Tải cấu hình, đăng ký handlers và chạy bot ở chế độ Polling (phát triển).
"""
from __future__ import annotations

try:
    from mavrykbot.bootstrap import ensure_project_root
except ModuleNotFoundError as exc:
    if exc.name not in {"mavrykbot", "mavrykbot.bootstrap"}:
        raise
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mavrykbot.bootstrap import ensure_project_root

ensure_project_root()

import logging
import os
from typing import Awaitable, Callable, Optional
from mavrykbot.handlers.view_due_orders import test_due_orders_command
from telegram import Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# ====================================================================
# SỬA LỖI TƯƠNG THÍCH PYTHON-TELEGRAM-BOT 20.x (Nếu cần)
# ====================================================================
# Đây là phần code đã có trong main.py gốc của bạn, dùng để vá lỗi
# tương thích với các phiên bản Python mới hơn.
try:
    import telegram.ext as _ptb_ext
    from telegram.ext import (
        _application as _ptb_application,
        _applicationbuilder as _ptb_applicationbuilder,
        _updater as _ptb_updater,
    )

    def _ensure_slots(cls, *extra_slots):
        slots = getattr(cls, "__slots__", ())
        missing = tuple(slot for slot in extra_slots if slot not in slots)
        if not isinstance(slots, tuple) or not missing:
            return cls
        patched = type(cls.__name__, (cls,), {"__slots__": slots + missing})
        patched.__module__ = cls.__module__
        return patched

    patched_updater = _ensure_slots(_ptb_updater.Updater, "__polling_cleanup_cb")
    if patched_updater is not _ptb_updater.Updater:
        _ptb_updater.Updater = patched_updater
        _ptb_applicationbuilder.Updater = patched_updater
        _ptb_ext.Updater = patched_updater

    patched_application = _ensure_slots(_ptb_application.Application, "__weakref__")
    if patched_application is not _ptb_application.Application:
        _ptb_application.Application = patched_application
        _ptb_applicationbuilder.Application = patched_application
except ImportError:
    pass
# ====================================================================


# --- IMPORTS ĐÃ ĐƯỢC CHỈNH SỬA THEO CẤU TRÚC PACKAGE MỚI ---
from mavrykbot.core.config import load_bot_config 
from mavrykbot.handlers.menu import show_outer_menu, show_main_selector
from mavrykbot.handlers.add_order import get_add_order_conversation_handler
from mavrykbot.handlers.update_order import get_update_order_conversation_handler
from mavrykbot.handlers.View_order_unpaid import get_unpaid_order_conversation_handler
from mavrykbot.handlers.Payment_Supply import get_payment_supply_conversation_handler
try:
    # Giả định qr_conversation nằm trong create_qrcode.py
    from mavrykbot.handlers.create_qrcode import qr_conversation 
except ImportError:
    # Dùng CommandHandler mặc định nếu file chưa tồn tại
    qr_conversation = CommandHandler("qr_placeholder", lambda u, c: c.bot.send_message(u.effective_chat.id, "Tính năng QR chưa hoàn thiện."))

# --- CẤU HÌNH LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- TẢI CẤU HÌNH BOT ---
# BOT_TOKEN sẽ được tải khi mavrykbot.core.config được import
BOT_TOKEN = load_bot_config().token

# --- CẤU HÌNH CHUNG ---
_admin_chat_id = os.getenv("ADMIN_CHAT_ID")
AUTHORIZED_USER_ID: Optional[int] = int(_admin_chat_id) if _admin_chat_id else None
DEFAULT_COMING_SOON = "Tính năng này đang được phát triển, vui lòng quay lại sau."
COMING_SOON_MESSAGES = {
    "start_refund": "Hoàn tiền đang được phát triển.",
    "update": "Tính năng xem/chỉnh đơn sẽ sớm mở lại.",
    "nhap_hang": "Nhập hàng đang được phát triển.",
}

# --- FILTERS ---
def user_only_filter(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]):
    """Decorator để chỉ cho phép user được cấp quyền sử dụng bot."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if AUTHORIZED_USER_ID is not None and update.effective_user.id != AUTHORIZED_USER_ID:
            logger.info("Access denied for user %s (%s)", update.effective_user.id, update.effective_user.username)
            return
        return await func(update, context)
    return wrapper

# --- HELPER ---
async def _send_coming_soon(update: Update, feature_key: str):
    """Gửi tin nhắn thông báo tính năng sắp ra mắt."""
    message = COMING_SOON_MESSAGES.get(feature_key, DEFAULT_COMING_SOON)
    if update.callback_query:
        await update.callback_query.answer()
        await update.effective_chat.send_message(message)
    else:
        await update.message.reply_text(message)
    logger.info("Sent coming-soon message for %s", feature_key)


# --- HANDLERS ---
@user_only_filter
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_outer_menu(update, context)


@user_only_filter
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot hiện chỉ hiển thị menu. Các chức năng khác đang được phát triển."
    )


@user_only_filter
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Phản hồi query để loại bỏ spinner 'loading'
    await query.answer() 
    
    if data == "menu_shop":
        await show_main_selector(update, context, edit=True)
        return
    if data == "back_to_menu":
        await show_outer_menu(update, context)
        return
    if data == "cancel_update":
        await show_main_selector(update, context, edit=True)
        return
    if data.startswith("action_") or data in {"nav_next", "nav_prev"}:
        await query.answer("Vui long mo chuc nang /update truoc.", show_alert=True)
        return
    if data == "delete":
        return
    if data in {"add", "unpaid_orders", "exit_unpaid", "payment_source"}:
        # Các callback này đã có ConversationHandler riêng xử lý
        return
    
    # Xử lý các nút tính năng đang phát triển
    await _send_coming_soon(update, data)


def main() -> None:
    application = (
        Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()
    )
    
    # Đăng ký các Handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Conversation Handlers
    application.add_handler(get_add_order_conversation_handler())
    application.add_handler(get_update_order_conversation_handler())
    application.add_handler(get_unpaid_order_conversation_handler())
    application.add_handler(get_payment_supply_conversation_handler())
    application.add_handler(qr_conversation) 
    
    # Callback Query Handler (Xử lý các nút bấm)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("testjob", test_due_orders_command))
    # --- CHẾ ĐỘ CHẠY: POLLING (Tối ưu cho phát triển trên Windows) ---
    logger.info("Khởi động BOT ở chế độ Polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    # ----------------------------------------------------------------


if __name__ == "__main__":
    main()
