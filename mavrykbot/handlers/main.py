"""
Telegram bot entry point – menu + New Order (Hoàn thành / Hủy đơn).
Dùng cho run_bot.py (polling) hoặc tích hợp webhook sau.
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

from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telegram.error import Conflict

from mavrykbot.core.config import load_bot_config
from mavrykbot.handlers.menu import show_menu
from mavrykbot.handlers.new_order import register_new_order_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = load_bot_config().token

_admin_chat_id = os.getenv("ADMIN_CHAT_ID")
AUTHORIZED_USER_ID: Optional[int] = int(_admin_chat_id) if _admin_chat_id else None
COMING_SOON = "Tính năng đang được phát triển."


def user_only_filter(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
):
    """Chỉ cho phép user admin đã cấu hình truy cập bot."""

    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if AUTHORIZED_USER_ID is not None and update.effective_user.id != AUTHORIZED_USER_ID:
            logger.info(
                "Access denied for user %s (%s)",
                update.effective_user.id,
                update.effective_user.username,
            )
            return
        return await func(update, context)

    return wrapper


async def _send_coming_soon(update: Update):
    if update.callback_query:
        await update.callback_query.answer()
        await update.effective_chat.send_message(COMING_SOON)
    else:
        await update.message.reply_text(COMING_SOON)


@user_only_filter
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context)


@user_only_filter
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dùng /menu hoặc /start để mở menu.")


@user_only_filter
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback chung (menu, v.v.). New Order đã có handler riêng với pattern."""
    query = update.callback_query
    await query.answer()
    await _send_coming_soon(update)


async def application_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logger.warning("Polling stopped: another instance is running: %s", context.error)
        return
    logger.error("Unhandled exception.", exc_info=context.error)


def build_application() -> Application:
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
    )
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("help", help_command))
    # New Order (Hoàn thành / Hủy đơn) — đăng ký trước để pattern được ưu tiên
    register_new_order_handlers(application, user_only_filter)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(application_error_handler)
    return application
