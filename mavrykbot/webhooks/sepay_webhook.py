from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application
from waitress import serve

# Load bootstrap
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
from mavrykbot.core.database import insert_payment_receipt
from mavrykbot.handlers.main import build_application
from mavrykbot.webhooks.payment_webhook import payment_webhook_blueprint

logger = logging.getLogger(__name__)
app = Flask(__name__)
app.register_blueprint(payment_webhook_blueprint)

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

SEPAY_WEBHOOK_PATH = "/api/payment/notify"

DEFAULT_WEBHOOK_URL = "https://botapi.mavrykpremium.store/webhook"
WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or DEFAULT_WEBHOOK_URL).strip()
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET")

_parsed_url = urlparse(WEBHOOK_URL) if WEBHOOK_URL else None
TELEGRAM_WEBHOOK_PATH = (_parsed_url.path or "/webhook") if _parsed_url else "/webhook"

try:
    SEPAY_CFG = load_sepay_config()
except RuntimeError:
    logger.warning("SEPAY config not loaded.")
    SEPAY_CFG = None

# ----------------------------------------------------------------------
# VERIFY SEPAY SIGNATURE
# ----------------------------------------------------------------------

def verify_sepay_signature(request_body: bytes, signature: Optional[str]) -> bool:
    if not SEPAY_CFG or not SEPAY_CFG.webhook_secret or not signature:
        return False

    expected = hmac.new(
        SEPAY_CFG.webhook_secret.encode("utf-8"),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ----------------------------------------------------------------------
# TELEGRAM WEBHOOK (ASYNC)
# ----------------------------------------------------------------------

_telegram_app: Optional[Application] = None
_telegram_loop: Optional[asyncio.AbstractEventLoop] = None
_telegram_available = False
_telegram_lock = threading.Lock()


def _start_telegram_bot() -> None:
    """Starts Telegram webhook listener in a background async thread."""
    global _telegram_available

    assert _telegram_app and _telegram_loop

    asyncio.set_event_loop(_telegram_loop)

    try:
        _telegram_loop.run_until_complete(_telegram_app.initialize())
        _telegram_loop.run_until_complete(_telegram_app.start())

        if WEBHOOK_URL:
            _telegram_loop.run_until_complete(
                _telegram_app.bot.set_webhook(
                    url=WEBHOOK_URL,
                    secret_token=WEBHOOK_SECRET,
                )
            )

        logger.info("Telegram webhook ready at %s", TELEGRAM_WEBHOOK_PATH)
        _telegram_available = True

        _telegram_loop.run_forever()

    except Exception as exc:
        logger.error("Telegram startup failed: %s", exc, exc_info=True)
        _telegram_available = False


def _ensure_telegram_initialized() -> None:
    """Ensures Telegram bot is initialized exactly once."""
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


# ----------------------------------------------------------------------
# FIX FOR FLASK 3.x (before_first_request removed)
# ----------------------------------------------------------------------

_bootstrap_done = False

@app.before_request
def _bootstrap_services():
    """Bootstrap Telegram service only once when the first request arrives."""
    global _bootstrap_done
    if not _bootstrap_done:
        _ensure_telegram_initialized()
        _bootstrap_done = True


# ----------------------------------------------------------------------
# ROUTES
# ----------------------------------------------------------------------

@app.route("/", methods=["GET"])
def healthcheck():
    return jsonify({
        "status": "ok",
        "telegram_ready": _telegram_available,
    }), 200


@app.route(TELEGRAM_WEBHOOK_PATH, methods=["GET", "POST"])
def telegram_webhook_receiver():
    _ensure_telegram_initialized()

    if request.method == "GET":
        return jsonify({
            "status": "ready" if _telegram_available else "starting"
        }), 200

    if not _telegram_available:
        return jsonify({"message": "Telegram not ready"}), 503

    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
        return jsonify({"message": "Forbidden"}), 403

    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"message": "Invalid JSON"}), 400

    try:
        update = Update.de_json(payload, _telegram_app.bot)
        asyncio.run_coroutine_threadsafe(
            _telegram_app.process_update(update),
            _telegram_loop
        )
    except Exception as exc:
        logger.error("Telegram update dispatch failed: %s", exc)
        return jsonify({"message": "Internal error"}), 500

    return jsonify({"message": "OK"}), 200


@app.route(SEPAY_WEBHOOK_PATH, methods=["POST"])
def sepay_webhook_receiver():
    raw_body = request.get_data()
    signature = request.headers.get("X-SEPAY-SIGNATURE")

    if not verify_sepay_signature(raw_body, signature):
        return jsonify({"message": "Invalid Signature"}), 403

    try:
        data = json.loads(raw_body.decode())
        transaction_data = data.get("transaction")
        if not transaction_data:
            return jsonify({"message": "Missing transaction"}), 400
    except json.JSONDecodeError:
        return jsonify({"message": "Invalid JSON"}), 400

    try:
        insert_payment_receipt(transaction_data)
        return jsonify({"message": "OK"}), 200
    except Exception as exc:
        logger.error("Error saving payment: %s", exc)
        return jsonify({"message": "Internal Error"}), 500


# ----------------------------------------------------------------------
# MAIN SERVER
# ----------------------------------------------------------------------

if __name__ == "__main__":
    host = os.getenv("SEPAY_HOST", "0.0.0.0")
    port = int(os.getenv("SEPAY_PORT", "5000"))

    print(f"Listening on http://{host}:{port}{SEPAY_WEBHOOK_PATH}")
    serve(app, host=host, port=port)
