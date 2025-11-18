from __future__ import annotations

import logging
from typing import Any, Mapping

from telegram import Bot

from mavrykbot.core.utils import escape_mdv2

__all__ = ["send_renewal_success_notification"]

logger = logging.getLogger(__name__)

NOTIFICATION_GROUP_ID = "-1002934465528"
RENEWAL_TOPIC_ID = 2


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
        return f"\n- *Slot:* {escape_mdv2(slot_data)}"
    return ""


async def send_renewal_success_notification(
    bot: Bot,
    order_details: Mapping[str, Any] | None,
    *,
    target_chat_id: str = NOTIFICATION_GROUP_ID,
    target_topic_id: int = RENEWAL_TOPIC_ID,
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

    try:
        ma_don_hang = escape_mdv2(order_details.get("ID_DON_HANG"))
        san_pham = escape_mdv2(order_details.get("SAN_PHAM"))
        thong_tin_don = escape_mdv2(order_details.get("THONG_TIN_DON"))
        ngay_dang_ky = escape_mdv2(order_details.get("NGAY_DANG_KY"))
        ngay_het_han = escape_mdv2(order_details.get("HET_HAN"))
        nguon = escape_mdv2(order_details.get("NGUON"))

        gia_nhap = _format_currency(order_details.get("GIA_NHAP"))
        gia_ban = _format_currency(order_details.get("GIA_BAN"))

        slot_section = _build_slot_section(order_details)

        message = (
            "*GIA HAN TU DONG THANH CONG*\n\n"
            "*Thong Tin Don Hang*\n"
            f"- *Ma Don:* `{ma_don_hang}`\n"
            f"- *San pham:* {san_pham}\n"
            f"- *Thong tin:* {thong_tin_don}"
            f"{slot_section}\n"
            f"- *Ngay DK Moi:* {ngay_dang_ky}\n"
            f"- *Het Han Moi:* *{ngay_het_han}*\n"
            f"- *Gia Ban:* {escape_mdv2(gia_ban)}d\n\n"
            "*Thong Tin Nguon*\n"
            f"- *Nguon:* {nguon}\n"
            f"- *Gia Nhap:* {escape_mdv2(gia_nhap)}d"
        )

        await bot.send_message(
            chat_id=target_chat_id,
            text=message,
            parse_mode="MarkdownV2",
            message_thread_id=target_topic_id,
        )
        logger.info(
            "Da gui thong bao gia han cho %s vao topic %s.",
            order_details.get("ID_DON_HANG"),
            target_topic_id,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Loi khi gui thong bao gia han %s: %s",
            order_details.get("ID_DON_HANG"),
            exc,
            exc_info=True,
        )
