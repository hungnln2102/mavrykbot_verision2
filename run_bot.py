"""Entry point to run the Telegram bot features (add/view/update orders, payment supply)."""
from __future__ import annotations

import asyncio
import logging

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root
from mavrykbot.handlers.main import build_application


async def main() -> None:
    ensure_project_root()
    ensure_env_loaded()

    app = build_application()
    logging.info("Starting Telegram bot in polling mode...")
    await app.initialize()
    await app.start()

    # Ensure no webhook is set and drop any pending updates before polling
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:  # pragma: no cover - network failure
        logging.warning("Failed to delete webhook before polling: %s", exc)

    updater = app.updater
    try:
        await updater.start_polling()
        await updater.stop()  # blocks until stopped
    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
