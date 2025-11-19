from __future__ import annotations

import logging
import traceback
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut

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

    body_lines_md = [f"*BOT LỖI:* {escape_mdv2(message)}"]
    body_lines_plain = [f"BOT LỖI: {message}"]

    if exception is not None:
        exc_text = "".join(traceback.format_exception(exception)).strip()
        body_lines_md.append("")
        body_lines_md.append("*Chi tiết:*")
        body_lines_md.append(escape_mdv2(exc_text))

        body_lines_plain.append("")
        body_lines_plain.append("Chi tiết:")
        body_lines_plain.append(exc_text)

    if extra:
        body_lines_md.append("")
        body_lines_md.append("*Ngữ cảnh:*")
        body_lines_plain.append("")
        body_lines_plain.append("Ngữ cảnh:")
        for key, value in extra.items():
            escaped_key = escape_mdv2(str(key))
            escaped_value = escape_mdv2(value)
            body_lines_md.append(f"\\- *{escaped_key}:* {escaped_value}")
            body_lines_plain.append(f"- {key}: {value}")

    text_md = "\n".join(body_lines_md)
    text_plain = "\n".join(body_lines_plain)
    try:
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=topic_id,
            text=text_md,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except BadRequest as exc:
        logger.warning("Markdown notification failed (%s). Retrying without formatting.", exc)
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=topic_id,
            text=text_plain,
        )
    except (RetryAfter, TimedOut, NetworkError) as exc:
        logger.error("Temporary error while sending notification: %s", exc, exc_info=True)
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to deliver error notification: %s", exc, exc_info=True)
