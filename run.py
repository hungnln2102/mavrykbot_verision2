from __future__ import annotations

import os
import threading

from waitress import serve

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root

ensure_project_root()
ensure_env_loaded()

from mavrykbot.handlers.main import run_bot_webhook
from mavrykbot.webhooks.sepay_webhook import SEPAY_WEBHOOK_PATH, app

DEFAULT_WEBHOOK_URL = "https://botapi.mavrykpremium.store/webhook"


def _start_sepay_server() -> None:
    host = os.getenv("SEPAY_HOST", "0.0.0.0")
    port = int(os.getenv("SEPAY_PORT", "5000"))
    print(f"Starting Sepay webhook server on http://{host}:{port}{SEPAY_WEBHOOK_PATH}")
    serve(app, host=host, port=port)


def _collect_webhook_config() -> tuple[str, str, int, str | None, str | None]:
    webhook_url = (os.getenv("WEBHOOK_URL") or DEFAULT_WEBHOOK_URL).strip()

    listen = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", "8443"))
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or os.getenv("WEBHOOK_SECRET")
    webhook_path = (os.getenv("WEBHOOK_PATH") or "").strip() or None
    return webhook_url, listen, port, webhook_path, secret


if __name__ == "__main__":
    print("=======================================================")
    print("Launching Sepay + Telegram webhook services")
    print("=======================================================")

    sepay_thread = threading.Thread(target=_start_sepay_server, daemon=True)
    sepay_thread.start()

    webhook_url, listen, port, webhook_path, secret = _collect_webhook_config()
    run_bot_webhook(
        webhook_url=webhook_url,
        listen=listen,
        port=port,
        webhook_path=webhook_path,
        secret_token=secret,
    )
