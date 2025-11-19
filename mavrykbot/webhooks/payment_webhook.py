from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Iterable

from aiohttp import web
from telegram import Bot

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PAYMENT_RECEIPT_TABLE,
    OrderListColumns,
    PaymentReceiptColumns,
)
from mavrykbot.handlers.renewal_logic import run_renewal
from mavrykbot.notifications.Notify_RenewOrder import send_renewal_success_notification

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = "ef3ff711d58d498aa6147d60eb3923df"

routes = web.RouteTableDef()


def extract_ma_don(text: str | None) -> list[str]:
    """Return all MAV*** order codes found inside a free-text content string."""
    if not text:
        return []
    return sorted({match.upper() for match in re.findall(r"MAV\w{5,}", text)})


def _normalize_amount(value) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits.isdigit() else 0


def _parse_transaction_date(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _insert_payment_receipt(order_codes: Iterable[str], payment_data: dict) -> None:
    ma_don_str = " - ".join(order_codes)
    ngay_thanh_toan = _parse_transaction_date(payment_data.get("transactionDate")).date()
    so_tien = _normalize_amount(payment_data.get("transferAmount"))
    nguoi_gui = str(payment_data.get("accountNumber") or "").strip()
    noi_dung = payment_data.get("content", "")

    sql = f"""
        INSERT INTO {PAYMENT_RECEIPT_TABLE} (
            {PaymentReceiptColumns.MA_DON_HANG},
            {PaymentReceiptColumns.NGAY_THANH_TOAN},
            {PaymentReceiptColumns.SO_TIEN},
            {PaymentReceiptColumns.NGUOI_GUI},
            {PaymentReceiptColumns.NOI_DUNG_CK}
        ) VALUES (%s, %s, %s, %s, %s)
    """
    db.execute(sql, (ma_don_str, ngay_thanh_toan, so_tien, nguoi_gui, noi_dung))
    logger.info("Logged payment receipt for orders: %s", ma_don_str or "N/A")


def _mark_order_paid(order_code: str) -> None:
    sql = f"""
        UPDATE {ORDER_LIST_TABLE}
        SET
            {OrderListColumns.TINH_TRANG} = %s,
            {OrderListColumns.CHECK_FLAG} = 'True'
        WHERE {OrderListColumns.ID_DON_HANG} = %s
    """
    db.execute(sql, ("Đã Thanh Toán", order_code))


def process_payment(bot: Bot, payment_data: dict, loop: asyncio.AbstractEventLoop) -> None:
    """Run inside a worker thread so the aiohttp handler can return quickly."""
    try:
        content = payment_data.get("content", "")
        ma_don_list = extract_ma_don(content)
        logger.info("Processing payment webhook for content: %s", content)

        try:
            _insert_payment_receipt(ma_don_list, payment_data)
        except Exception as exc:
            logger.error("Failed to log payment receipt: %s", exc, exc_info=True)

        if not ma_don_list:
            logger.info("No order code detected, nothing else to do.")
            return

        for ma_don in ma_don_list:
            try:
                _mark_order_paid(ma_don)
            except Exception as exc:
                logger.warning("Could not mark %s as paid: %s", ma_don, exc)

            success, details, process_type = run_renewal(ma_don)
            if success and process_type == "renewal":
                logger.info("Renewal succeeded for %s. Scheduling Telegram notice.", ma_don)
                asyncio.run_coroutine_threadsafe(
                    send_renewal_success_notification(bot, details),
                    loop,
                )
            else:
                logger.info(
                    "Renewal skipped for %s (status=%s, details=%s).",
                    ma_don,
                    process_type,
                    details,
                )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Critical error while processing payment webhook: %s", exc, exc_info=True)


@routes.post(f"/bot/payment_sepay/{WEBHOOK_SECRET}")
async def handle_payment(request: web.Request) -> web.StreamResponse:
    bot = request.app["bot"]
    try:
        data = await request.json()
    except Exception as exc:
        logger.error("Invalid JSON payload: %s", exc)
        return web.Response(text="Bad Request", status=400)

    current_loop = asyncio.get_running_loop()
    asyncio.create_task(
        asyncio.to_thread(
            process_payment,
            bot,
            data,
            current_loop,
        )
    )
    return web.Response(text="Webhook received", status=200)
