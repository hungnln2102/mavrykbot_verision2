from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application
from waitress import serve

try:
    from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root
except ModuleNotFoundError as exc:
    if exc.name not in {"mavrykbot", "mavrykbot.bootstrap"}:
        raise
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root

ensure_project_root()
ensure_env_loaded()

from mavrykbot.core.config import load_sepay_config
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import PAYMENT_RECEIPT_TABLE, PaymentReceiptColumns
from mavrykbot.handlers.main import build_application

logger = logging.getLogger(__name__)
app = Flask(__name__)

SEPAY_WEBHOOK_PATH = "/api/payment/notify"
DEFAULT_WEBHOOK_URL = "https://botapi.mavrykpremium.store/bot/webhook"
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or DEFAULT_WEBHOOK_URL).strip()
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET")
_parsed_url = urlparse(WEBHOOK_URL) if WEBHOOK_URL else None
TELEGRAM_WEBHOOK_PATH = (_parsed_url.path or "/bot/webhook") if _parsed_url else "/bot/webhook"

try:
    SEPAY_CFG = load_sepay_config()
except RuntimeError:
    logger.warning("SEPAY config not fully loaded. Webhook verification may fail.")
    SEPAY_CFG = None


def _split_transaction_content(content: str) -> Tuple[str, str]:
    parts = (content or "").strip().split()
    if not parts:
        raise ValueError("transaction_content is empty")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[-1], parts[0]


def verify_sepay_signature(request_body: bytes, signature: Optional[str]) -> bool:
    if not SEPAY_CFG or not SEPAY_CFG.webhook_secret or not signature:
        return False
    expected = hmac.new(
        SEPAY_CFG.webhook_secret.encode("utf-8"),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def insert_payment_receipt(transaction_data: Dict[str, Any]) -> None:
    order_code, sender = _split_transaction_content(
        transaction_data.get("transaction_content", "")
    )
    paid_date = datetime.strptime(
        transaction_data.get("transaction_date", ""),
        "%Y-%m-%d %H:%M:%S",
    ).date()
    amount = int(transaction_data.get("amount_in", "0").split(".")[0] or 0)

    sql = f"""
        INSERT INTO {PAYMENT_RECEIPT_TABLE} (
            {PaymentReceiptColumns.MA_DON_HANG},
            {PaymentReceiptColumns.NGAY_THANH_TOAN},
            {PaymentReceiptColumns.SO_TIEN},
            {PaymentReceiptColumns.NGUOI_GUI},
            {PaymentReceiptColumns.NOI_DUNG_CK}
        ) VALUES (%s, %s, %s, %s, %s)
    """
    db.execute(
        sql,
        (
            order_code,
            paid_date,
            amount,
            sender,
            transaction_data.get("transaction_content", ""),
        ),
    )
    logger.info("Saved payment receipt for order %s", order_code)


# ----------------------------------------------------------------------
# Telegram webhook integration
# ----------------------------------------------------------------------

_telegram_app: Optional[Application] = None
_telegram_loop: Optional[asyncio.AbstractEventLoop] = None
_telegram_available = False
_telegram_lock = threading.Lock()


def _start_telegram_bot() -> None:
    assert _telegram_app and _telegram_loop
    asyncio.set_event_loop(_telegram_loop)
    try:
        _telegram_loop.run_until_complete(_telegram_app.initialize())
        _telegram_loop.run_until_complete(_telegram_app.start())
        if WEBHOOK_URL:
            _telegram_loop.run_until_complete(
                _telegram_app.bot.set_webhook(WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
            )
        logger.info("Telegram webhook dispatcher ready at %s", TELEGRAM_WEBHOOK_PATH)
        global _telegram_available
        _telegram_available = True
        _telegram_loop.run_forever()
    except Exception as exc:  # pragma: no cover
        _telegram_available = False
        logger.error("Failed to start Telegram bot loop: %s", exc, exc_info=True)


def _ensure_telegram_initialized() -> None:
    global _telegram_app, _telegram_loop
    if _telegram_loop and _telegram_available:
        return
    with _telegram_lock:
        if _telegram_loop:
            return
        _telegram_app = build_application()
        _telegram_loop = asyncio.new_event_loop()
        threading.Thread(
            target=_start_telegram_bot,
            name="telegram-webhook",
            daemon=True,
        ).start()


@app.before_first_request
def _bootstrap_services() -> None:
    _ensure_telegram_initialized()


def _dispatch_telegram_update(payload: Dict[str, Any]) -> None:
    if not (_telegram_app and _telegram_loop and _telegram_available):
        raise RuntimeError("Telegram loop is not available")
    update = Update.de_json(payload, _telegram_app.bot)
    asyncio.run_coroutine_threadsafe(
        _telegram_app.process_update(update),
        _telegram_loop,
    )


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({"status": "ok", "telegram_ready": _telegram_available}), 200


@app.route(TELEGRAM_WEBHOOK_PATH, methods=["GET", "POST"])
def telegram_webhook_receiver():
    _ensure_telegram_initialized()
    if request.method == "GET":
        return jsonify({"status": "ready" if _telegram_available else "starting"}), 200
    if not _telegram_available:
        return jsonify({"message": "Telegram webhook is not ready"}), 503

    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
        logger.warning("Rejected Telegram webhook due to secret mismatch.")
        return jsonify({"message": "Forbidden"}), 403

    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"message": "Invalid JSON"}), 400

    try:
        _dispatch_telegram_update(payload)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to dispatch Telegram update: %s", exc, exc_info=True)
        return jsonify({"message": "Internal Server Error"}), 500

    return jsonify({"message": "OK"}), 200


@app.route(SEPAY_WEBHOOK_PATH, methods=["POST"])
def sepay_webhook_receiver():
    raw_body = request.get_data()
    signature = request.headers.get("X-SEPAY-SIGNATURE")

    if not verify_sepay_signature(raw_body, signature):
        logger.error("Sepay Webhook signature verification failed.")
        return jsonify({"message": "Invalid Signature"}), 403

    try:
        data = json.loads(raw_body.decode("utf-8"))
        transaction_data = data.get("transaction")
        if not transaction_data:
            return jsonify({"message": "Missing Transaction Data"}), 400
    except json.JSONDecodeError:
        return jsonify({"message": "Invalid JSON"}), 400

    try:
        insert_payment_receipt(transaction_data)
        return jsonify({"message": "OK"}), 200
    except Exception as exc:
        logger.error("Error processing and saving data: %s", exc, exc_info=True)
        return jsonify({"message": "Internal Server Error"}), 500


if __name__ == "__main__":
    host = os.getenv("SEPAY_HOST", "0.0.0.0")
    port = int(os.getenv("SEPAY_PORT", "5000"))
    print(f"Listening on http://{host}:{port}{SEPAY_WEBHOOK_PATH}")
    serve(app, host=host, port=port)
