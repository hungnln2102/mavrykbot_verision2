"""
Telegram bot entry point.
Sets up handlers and provides the Application builder function for webhook mode.
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
from urllib.parse import urlparse

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

from telegram import Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from mavrykbot.core.config import load_bot_config
from mavrykbot.handlers.Payment_Supply import get_payment_supply_conversation_handler
from mavrykbot.handlers.View_order_unpaid import get_unpaid_order_conversation_handler
from mavrykbot.handlers.add_order import get_add_order_conversation_handler
from mavrykbot.handlers.menu import show_main_selector, show_outer_menu
from mavrykbot.handlers.update_order import get_update_order_conversation_handler
from mavrykbot.handlers.view_due_orders import test_due_orders_command
from mavrykbot.notifications.error_notifier import notify_error

try:
    from mavrykbot.handlers.create_qrcode import qr_conversation
except ImportError:  # pragma: no cover - optional feature
    qr_conversation = CommandHandler(
        "qr_placeholder",
        lambda update, context: context.bot.send_message(
            update.effective_chat.id,
            "QR feature is not available yet.",
        ),
    )

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = load_bot_config().token

_admin_chat_id = os.getenv("ADMIN_CHAT_ID")
AUTHORIZED_USER_ID: Optional[int] = int(_admin_chat_id) if _admin_chat_id else None
DEFAULT_COMING_SOON = "Feature is under development."
COMING_SOON_MESSAGES = {
    "start_refund": "Refund flow is under development.",
    "update": "Order update feature will be back soon.",
}


def user_only_filter(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
):
    """Decorator restricting bot access to the configured admin."""

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


async def _send_coming_soon(update: Update, feature_key: str):
    """Send placeholder message for unfinished flows."""
    message = COMING_SOON_MESSAGES.get(feature_key, DEFAULT_COMING_SOON)
    if update.callback_query:
        await update.callback_query.answer()
        await update.effective_chat.send_message(message)
    else:
        await update.message.reply_text(message)
    logger.info("Sent coming-soon message for %s", feature_key)


@user_only_filter
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_outer_menu(update, context)


@user_only_filter
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please use /menu to interact with the bot.")


@user_only_filter
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
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
        await query.answer("Please open /update first.", show_alert=True)
        return
    if data == "delete":
        return
    if data in {"add", "unpaid_orders", "exit_unpaid", "payment_source"}:
        return

    await _send_coming_soon(update, data)


async def application_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception while processing update.", exc_info=context.error)
    error_message = "Bot encountered an unexpected error."
    extra = {"update": str(update)} if update else None

    try:
        await notify_error(
            context.bot,
            error_message,
            exception=context.error,
            extra=extra,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to notify error topic: %s", exc, exc_info=True)


def build_application() -> Application:
    """Xây dựng và trả về đối tượng Application để sử dụng cho Webhook."""
    application = (
        Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(get_add_order_conversation_handler())
    application.add_handler(get_update_order_conversation_handler())
    application.add_handler(get_unpaid_order_conversation_handler())
    application.add_handler(get_payment_supply_conversation_handler())
    application.add_handler(qr_conversation)

    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("testjob", test_due_orders_command))
    application.add_error_handler(application_error_handler)
    return application