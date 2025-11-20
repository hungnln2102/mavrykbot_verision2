from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import unicodedata
from datetime import datetime
from typing import Iterable, Mapping, Tuple, Optional

from flask import Blueprint, jsonify, request
from telegram import Bot

from mavrykbot.core.config import load_bot_config
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PAYMENT_SUPPLY_TABLE,
    PAYMENT_RECEIPT_TABLE,
    PRODUCT_PRICE_TABLE,
    SUPPLY_PRICE_TABLE,
    OrderListColumns,
    PaymentReceiptColumns,
    PaymentSupplyColumns,
    ProductPriceColumns,
    SupplyPriceColumns,
    SUPPLY_TABLE,
    SupplyColumns,
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


def _get_payload_value(data: Mapping[str, object], *keys: str) -> object | None:
    """Fetch a value from the payload using a list of candidate keys (case-insensitive)."""
    if not data:
        return None
    lowered = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        if key in data:
            return data[key]
        lower_key = key.lower()
        if lower_key in lowered:
            return lowered[lower_key]
    return None


def _normalize_amount(value) -> int:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits.isdigit() else 0


def _normalize_source_name(value: str | None) -> str:
    """Lowercase source name and trim whitespace, keeping accents and @."""
    if not value:
        return ""
    return str(value).strip().lower()


def _strip_accents(value: str) -> str:
    """Remove Vietnamese accents for more robust status comparisons."""
    if not value:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _find_product_id_for_orders(order_codes: Iterable[str]) -> Optional[int]:
    """
    Given a list of order codes, find the first matching product_id
    (via product_price) for use when looking up supply_price.
    """
    for code in order_codes:
        sql = f"""
            SELECT pp.{ProductPriceColumns.ID}
            FROM {ORDER_LIST_TABLE} ol
            JOIN {PRODUCT_PRICE_TABLE} pp
                ON LOWER(pp.{ProductPriceColumns.SAN_PHAM}) = LOWER(ol.{OrderListColumns.SAN_PHAM})
            WHERE LOWER(ol.{OrderListColumns.ID_DON_HANG}) = LOWER(%s)
            LIMIT 1
        """
        row = db.fetch_one(sql, (code,))
        if row and row[0]:
            return int(row[0])
    return None


def _fetch_supply_price(source_id: int, product_id: int) -> Optional[int]:
    """Fetch the latest supply_price for the given source/product pair."""
    sql = f"""
        SELECT {SupplyPriceColumns.PRICE}
        FROM {SUPPLY_PRICE_TABLE}
        WHERE {SupplyPriceColumns.SOURCE_ID} = %s
          AND {SupplyPriceColumns.PRODUCT_ID} = %s
        ORDER BY {SupplyPriceColumns.ID} DESC
        LIMIT 1
    """
    row = db.fetch_one(sql, (source_id, product_id))
    if row and row[0] is not None:
        return _normalize_amount(row[0])
    return None


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
    ngay_thanh_toan = _parse_transaction_date(
        _get_payload_value(payment_data, "transactionDate", "transaction_date")
    ).date()
    so_tien = _normalize_amount(_get_payload_value(payment_data, "transferAmount", "amount_in", "amount"))
    nguoi_gui = str(_get_payload_value(payment_data, "accountNumber", "accountnumber", "fromAccount") or "").strip()
    noi_dung = str(_get_payload_value(payment_data, "content", "transaction_content", "description") or "")

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


def _find_source_from_content(content: str) -> Tuple[int | None, str | None]:
    """
    Try to match a source_name from the supply table using the payment content.
    Matching is case-insensitive but keeps accents/@ for exactness.
    """
    normalized_content = " ".join((content or "").lower().split())

    sql = f"SELECT {SupplyColumns.ID}, {SupplyColumns.SOURCE_NAME} FROM {SUPPLY_TABLE}"
    for source_id, source_name in db.fetch_all(sql):
        normalized_source = _normalize_source_name(source_name)
        if not normalized_source:
            continue
        if f" {normalized_source} " in f" {normalized_content} " or normalized_source in normalized_content:
            return int(source_id), str(source_name or "")
    return None, None


def _sync_payment_supply(source_id: int, amount: int) -> None:
    """
    Update payment_supply rows based on Sepay transfer.
    - If the latest row for the source is pending, add the amount to its import.
    - Otherwise, insert a fresh row with today's round label and empty status/paid.
    """
    if not source_id or amount <= 0:
        return

    select_sql = f"""
        SELECT {PaymentSupplyColumns.ID}, {PaymentSupplyColumns.IMPORT}, {PaymentSupplyColumns.STATUS}
        FROM {PAYMENT_SUPPLY_TABLE}
        WHERE {PaymentSupplyColumns.SOURCE_ID} = %s
        ORDER BY {PaymentSupplyColumns.ID} DESC
        LIMIT 1
    """
    row = db.fetch_one(select_sql, (source_id,))
    if row:
        payment_id, import_value, status_value = row
        status_text = str(status_value or "").strip().casefold()
        if status_text == "chưa thanh toán":
            current_import = _normalize_amount(import_value)
            new_import = current_import + amount
            update_sql = f"""
                UPDATE {PAYMENT_SUPPLY_TABLE}
                SET {PaymentSupplyColumns.IMPORT} = %s
                WHERE {PaymentSupplyColumns.ID} = %s
            """
            db.execute(update_sql, (new_import, payment_id))
            logger.info("Updated pending payment_supply #%s new import=%s", payment_id, new_import)
            return

    round_label = datetime.now().strftime("%d/%m/%Y")
    insert_sql = f"""
        INSERT INTO {PAYMENT_SUPPLY_TABLE} (
            {PaymentSupplyColumns.SOURCE_ID},
            {PaymentSupplyColumns.IMPORT},
            {PaymentSupplyColumns.ROUND},
            {PaymentSupplyColumns.PAID},
            {PaymentSupplyColumns.STATUS}
        ) VALUES (%s, %s, %s, %s, %s)
    """
    db.execute(insert_sql, (source_id, amount, round_label, None, None))
    logger.info("Inserted new payment_supply row for source_id=%s import=%s", source_id, amount)


def process_payment_payload(payment_data: Mapping[str, object]) -> None:
    """
    Process Sepay webhook data: log receipts, mark orders, and trigger renewals.

    This function is blocking and should run in a worker thread so the HTTP
    response can be returned quickly.
    """
    try:
        content = str(_get_payload_value(payment_data, "content", "transaction_content", "description") or "")
        ma_don_list = extract_ma_don(content)
        logger.info("Processing payment webhook for content: %s", content)

        try:
            _insert_payment_receipt(ma_don_list, payment_data)
        except Exception as exc:
            logger.error("Failed to log payment receipt: %s", exc, exc_info=True)

        try:
            source_id, source_name = _find_source_from_content(content)
            product_id = _find_product_id_for_orders(ma_don_list)
            supply_price_value: Optional[int] = None
            if source_id and product_id:
                supply_price_value = _fetch_supply_price(source_id, product_id)

            # Fallback to transfer amount only if no supply price found
            amount_value = supply_price_value
            if amount_value is None:
                amount_value = _normalize_amount(_get_payload_value(payment_data, "transferAmount", "amount_in", "amount"))

            if source_id and amount_value and amount_value > 0:
                _sync_payment_supply(source_id, amount_value)
            else:
                logger.info(
                    "No matching source/price found (source=%s, product_id=%s, amount=%s).",
                    source_name,
                    product_id,
                    amount_value,
                )
        except Exception as exc:
            logger.error("Failed to sync payment_supply from webhook: %s", exc, exc_info=True)

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
