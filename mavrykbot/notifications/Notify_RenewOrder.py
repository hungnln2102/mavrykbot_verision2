from __future__ import annotations

import logging
from typing import Any, Mapping

from telegram import Bot
from telegram.constants import ParseMode

from mavrykbot.core.config import load_topic_config
from mavrykbot.core.utils import escape_mdv2

__all__ = ["send_renewal_success_notification", "send_renewal_status_notification"]

logger = logging.getLogger(__name__)

DEFAULT_NOTIFICATION_GROUP_ID = "-1002934465528"
DEFAULT_RENEWAL_TOPIC_ID = 2

TOPIC_CONFIG = load_topic_config()


def _resolve_target(chat_id: str | None, topic_id: int | None) -> tuple[str | None, int | None]:
    resolved_chat = chat_id or TOPIC_CONFIG.renewal_group_id or DEFAULT_NOTIFICATION_GROUP_ID
    topic_source = topic_id if topic_id is not None else (TOPIC_CONFIG.renewal_topic_id or DEFAULT_RENEWAL_TOPIC_ID)
    try:
        resolved_topic = int(topic_source)
    except (TypeError, ValueError):
        resolved_topic = None
    return resolved_chat, resolved_topic


def _format_currency(value: Any) -> str:
    """Format arbitrary numeric input into a readable currency string."""
    try:
        number = float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return "0"
    return "{:,.0f}".format(number)


def _build_slot_section(order_details: Mapping[str, Any]) -> str:
    slot_data = order_details.get("SLOT")
    if slot_data and str(slot_data).strip():
        return f"🎟️ *Slot:* {escape_mdv2(slot_data)}"
    return ""


async def send_renewal_success_notification(
    bot: Bot,
    order_details: Mapping[str, Any] | None,
    *,
    target_chat_id: str | None = None,
    target_topic_id: int | None = None,
) -> None:
    """
    Notify the renewal topic when a background renewal succeeds.

    Parameters
    ----------
    bot:
        Telegram bot instance reused by the webhook consumer.
    order_details:
        Dictionary returned by `run_renewal` describing the renewed order.
    target_chat_id / target_topic_id:
        Allow overriding the destination when running manual tests.
    """
    if not order_details:
        logger.warning("send_renewal_success_notification was called without order details.")
        return

    if not TOPIC_CONFIG.send_renewal_to_topic:
        logger.info("Skipping renewal notification because SEND_RENEWAL_TO_TOPIC is disabled in config.")
        return

    target_chat_id, target_topic_id = _resolve_target(target_chat_id, target_topic_id)
    if not target_chat_id or target_topic_id is None:
        logger.error("Cannot send renewal notification: missing chat/topic configuration.")
        return

    try:
        ma_don_hang = escape_mdv2(order_details.get("ID_DON_HANG"))
        san_pham = escape_mdv2(order_details.get("SAN_PHAM"))
        thong_tin_don = escape_mdv2(order_details.get("THONG_TIN_DON"))
        ngay_dang_ky = escape_mdv2(order_details.get("NGAY_DANG_KY"))
        ngay_het_han = escape_mdv2(order_details.get("HET_HAN"))
        nguon = escape_mdv2(order_details.get("NGUON"))

        gia_nhap = _format_currency(order_details.get("GIA_NHAP"))
        gia_ban = _format_currency(order_details.get("GIA_BAN"))

        slot_line = _build_slot_section(order_details)

        lines = [
            "✅ *GIA HẠN TỰ ĐỘNG THÀNH CÔNG*",
            "┏━━━ *Thông Tin Đơn Hàng* ━━━┓",
            f"🆔 *Mã Đơn:* `{ma_don_hang}`",
            f"📦 *Sản Phẩm:* {san_pham}",
            f"📧 *Thông tin:* {thong_tin_don}",
        ]
        if slot_line:
            lines.append(slot_line)
        lines.extend(
            [
                f"📅 *Ngày Đăng Ký:* {ngay_dang_ky}",
                f"⏰ *Hết Hạn:* *{ngay_het_han}*",
                f"💰 *Giá Bán:* {escape_mdv2(gia_ban)}d",
                "",
                "┗━━━ *Thông Tin Nhà Cung Cấp* ━━━┛",
                f"🏷️ *Nhà Cung Cấp:* {nguon}",
                f"💵 *Giá Nhập:* {escape_mdv2(gia_nhap)}d",
            ]
        )

        message = "\n".join(lines)

        await bot.send_message(
            chat_id=target_chat_id,
            text=message,
            parse_mode="MarkdownV2",
            message_thread_id=target_topic_id,
        )
        logger.info(
            "Đã gửi thành công thông báo gia hạn cho %s vào topic Renew Order.",
            order_details.get("ID_DON_HANG"),
            target_topic_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Lỗi khi gửi thông báo gia hạn %s: %s",
            order_details.get("ID_DON_HANG"),
            exc,
            exc_info=True,
        )


async def send_renewal_status_notification(
    bot: Bot,
    order_code: str,
    status: str,
    *,
    details: str | None = None,
    target_chat_id: str | None = None,
    target_topic_id: int | None = None,
) -> None:
    """
    Send a short summary of the renewal status (success/skip/error) to the renewal topic.
    Useful when Sepay payment webhook handles an order but renewal logic does not run.
    """
    if not TOPIC_CONFIG.send_error_to_topic and not TOPIC_CONFIG.send_renewal_to_topic:
        return

    target_chat_id, target_topic_id = _resolve_error_target(target_chat_id, target_topic_id)
    if not target_chat_id or target_topic_id is None:
        logger.error("Cannot send renewal status notification: missing chat/topic configuration.")
        return

    try:
        message_lines = [
            "*Thông Báo Lỗi Khi Gia Hạn*",
            f"\\- Mã Đơn:* `{escape_mdv2(order_code)}`",
            f"\\- *Trạng Thái:* {escape_mdv2(status)}",
        ]
        if details:
            message_lines.append(f"\\- *Chi tiet:* {escape_mdv2(str(details))}")

        await bot.send_message(
            chat_id=target_chat_id,
            text="\n".join(message_lines),
            parse_mode=ParseMode.MARKDOWN_V2,
            message_thread_id=target_topic_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Lỗi khi gửi thông báo trạng thái gia hạn %s: %s",
            order_code,
            exc,
            exc_info=True,
        )
def _resolve_error_target(chat_id: str | None, topic_id: int | None) -> tuple[str | None, int | None]:
    resolved_chat = chat_id or TOPIC_CONFIG.error_group_id or TOPIC_CONFIG.renewal_group_id
    topic_source = topic_id if topic_id is not None else (
        TOPIC_CONFIG.error_topic_id if TOPIC_CONFIG.error_topic_id is not None else TOPIC_CONFIG.renewal_topic_id
    )
    try:
        resolved_topic = int(topic_source) if topic_source is not None else None
    except (TypeError, ValueError):
        resolved_topic = None
    return resolved_chat, resolved_topic
