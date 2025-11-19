from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from datetime import datetime
from typing import Iterable, Mapping

from flask import Blueprint, jsonify, request
from telegram import Bot

from mavrykbot.core.config import load_bot_config
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PAYMENT_RECEIPT_TABLE,
    OrderListColumns,
    PaymentReceiptColumns,
)
from mavrykbot.handlers.renewal_logic import run_renewal
from mavrykbot.notifications.Notify_RenewOrder import (
    send_renewal_status_notification,
    send_renewal_success_notification,
)

__all__ = ["payment_webhook_blueprint", "PAYMENT_WEBHOOK_PATH"]

logger = logging.getLogger(__name__)

PAYMENT_WEBHOOK_SECRET = (
    os.getenv("PAYMENT_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET") or "change-this-secret"
)
PAYMENT_WEBHOOK_PATH = f"/bot/payment_sepay/{PAYMENT_WEBHOOK_SECRET}"

payment_webhook_blueprint = Blueprint("payment_webhook", __name__)

_bot_instance: Bot | None = None
_bot_lock = threading.Lock()


def _get_bot() -> Bot:
    """Instantiate a Telegram Bot lazily so Waitress threads can reuse it."""
    global _bot_instance
    if _bot_instance:
        return _bot_instance
    with _bot_lock:
        if _bot_instance is None:
            _bot_instance = Bot(load_bot_config().token)
    return _bot_instance


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


def _insert_payment_receipt(order_codes: Iterable[str], payment_data: Mapping[str, object]) -> None:
    ma_don_str = " - ".join(order_codes)
    ngay_thanh_toan = _parse_transaction_date(payment_data.get("transactionDate")).date()
    so_tien = _normalize_amount(payment_data.get("transferAmount"))
    nguoi_gui = str(payment_data.get("accountNumber") or "").strip()
    noi_dung = str(payment_data.get("content") or "")

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


def _send_success_notification(order_details: Mapping[str, object]) -> None:
    """Send the full renewal summary when Sepay renewal succeeds."""
    try:
        asyncio.run(send_renewal_success_notification(_get_bot(), order_details))
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to send renewal success notification: %s", exc, exc_info=True)


def _send_status_notification(order_code: str, status: str, detail_text: str | None = None) -> None:
    """Send a lightweight status entry (success/skip/error) to the renewal topic."""
    try:
        asyncio.run(
            send_renewal_status_notification(
                _get_bot(),
                order_code,
                status,
                details=detail_text,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to send renewal status notification: %s", exc, exc_info=True)


def process_payment_payload(payment_data: Mapping[str, object]) -> None:
    """
    Process Sepay webhook data: log receipts, mark orders, and trigger renewals.

    This function is blocking and should run in a worker thread so the HTTP
    response can be returned quickly.
    """
    try:
        content = str(payment_data.get("content") or "")
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
            success, details, process_type = run_renewal(ma_don)
            if success and process_type == "renewal":
                logger.info("Renewal succeeded for %s. Sending Telegram notice.", ma_don)
                if details:
                    _send_success_notification(details)
                else:
                    _send_status_notification(ma_don, "success", "Khong co chi tiet don hang.")
            else:
                detail_text = details if isinstance(details, str) else str(details or "")
                status_text = process_type or "skipped"
                logger.info(
                    "Renewal skipped for %s (status=%s, details=%s).",
                    ma_don,
                    status_text,
                    detail_text,
                )
                _send_status_notification(ma_don, status_text, detail_text or None)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Critical error while processing payment webhook: %s", exc, exc_info=True)


@payment_webhook_blueprint.post(PAYMENT_WEBHOOK_PATH)
def handle_payment_webhook():
    """
    Lightweight HTTP handler that validates the payload and schedules processing.
    Designed to run inside the same Flask application served by Waitress.
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        logger.exception("Invalid JSON payload received from payment provider.")
        return jsonify({"message": "Invalid JSON"}), 400

    threading.Thread(
        target=process_payment_payload,
        args=(payload or {},),
        name="payment-webhook-worker",
        daemon=True,
    ).start()

    return jsonify({"message": "OK"}), 200
