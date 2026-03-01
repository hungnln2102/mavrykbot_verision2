"""Entry point to run the Telegram bot (polling mode)."""
from __future__ import annotations

import logging
from pathlib import Path

from telegram.error import Conflict

# Đường dẫn .env cố định theo vị trí run_bot.py (trùng với PM2 exec cwd)
_ENV_FILE = Path(__file__).resolve().parent / ".env"

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root, log_env_status
from mavrykbot.core.runtime import bot_instance_lock

# Load .env trước khi import main (để NOTIFY_ORDER_* có sẵn khi handler chạy)
ensure_project_root()
ensure_env_loaded(str(_ENV_FILE))
log_env_status(str(_ENV_FILE))

import os as _os
import sys as _sys
if not (_os.getenv("TELEGRAM_BOT_TOKEN") or "").strip():
    print(f"[MAVRYKBOT FATAL] Không đọc được TELEGRAM_BOT_TOKEN. File .env: {_ENV_FILE} (exists={_ENV_FILE.exists()})", file=_sys.stderr, flush=True)
    _sys.exit(1)

from mavrykbot.handlers.main import build_application


def _run_polling() -> None:
    """
    Run the bot using the built-in Application.run_polling lifecycle.

    python-telegram-bot v20+ no longer exposes Updater.wait(), so we delegate to
    Application.run_polling to manage the loop and shutdown sequence.
    """
    app = build_application()
    try:
        logging.info("Starting Telegram bot in polling mode...")
        app.run_polling(drop_pending_updates=True)
    except Conflict as exc:
        logging.error("Another bot instance is already polling this token: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected failures
        logging.error("Unexpected error while running the bot: %s", exc)


def main() -> None:
    ensure_project_root()
    ensure_env_loaded(str(_ENV_FILE))
    try:
        with bot_instance_lock():
            _run_polling()
    except RuntimeError as exc:
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
