"""Entry point to run the Telegram bot (polling mode)."""
from __future__ import annotations

import logging

from telegram.error import Conflict

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root
from mavrykbot.core.runtime import bot_instance_lock

# Load .env trước khi import main (để NOTIFY_ORDER_* có sẵn khi handler chạy)
ensure_project_root()
ensure_env_loaded()

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
    ensure_env_loaded()
    try:
        with bot_instance_lock():
            _run_polling()
    except RuntimeError as exc:
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
