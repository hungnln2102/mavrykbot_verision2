from __future__ import annotations

import logging
import traceback
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode

from mavrykbot.core.config import load_topic_config
from mavrykbot.core.utils import escape_mdv2

logger = logging.getLogger(__name__)
TOPIC_CONFIG = load_topic_config()


async def notify_error(bot: Bot, message: str, *, exception: Exception | BaseException | None = None, extra: dict[str, Any] | None = None) -> None:
    """
    Send a formatted error notification to the configured error topic.

    Parameters
    ----------
    bot:
        Telegram bot instance.
    message:
        Short human-readable description of the failure.
    exception:
        Optional exception to include in the payload.
    extra:
        Optional dictionary of extra context that will be rendered as key/value pairs.
    """
    if not TOPIC_CONFIG.send_error_to_topic:
        return

    chat_id = TOPIC_CONFIG.error_group_id
    topic_id = TOPIC_CONFIG.error_topic_id
    if not chat_id or topic_id is None:
        logger.warning("Error notification skipped due to missing chat/topic configuration.")
        return

    body_lines = [f"*BOT LỖI:* {escape_mdv2(message)}"]

    if exception is not None:
        exc_text = "".join(traceback.format_exception(exception)).strip()
        body_lines.append("")
        body_lines.append("*Chi tiết:*")
        body_lines.append(escape_mdv2(exc_text))

    if extra:
        body_lines.append("")
        body_lines.append("*Ngữ cảnh:*")
        for key, value in extra.items():
            body_lines.append(f"- *{escape_mdv2(str(key))}:* {escape_mdv2(value)}")

    text = "\n".join(body_lines)
    try:
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=topic_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to deliver error notification: %s", exc, exc_info=True)
