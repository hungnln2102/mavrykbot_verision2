"""Entry point to run the Telegram bot (polling mode)."""
from __future__ import annotations

import asyncio
import logging

from telegram.error import Conflict

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root
from mavrykbot.core.runtime import bot_instance_lock
from mavrykbot.handlers.main import build_application


async def _run_polling() -> None:
    app = build_application()
    try:
        # Clear any stale webhook configuration before switching to polling.
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:
        logging.warning("Could not clear webhook before polling: %s", exc)

    try:
        await app.initialize()
        await app.start()
        if app.updater is None:  # defensive guard; should not happen in polling mode
            raise RuntimeError("Application was built without an updater; polling is unavailable.")
        logging.info("Starting Telegram bot in polling mode...")
        await app.updater.start_polling(drop_pending_updates=True)
        await app.updater.wait()
    except Conflict as exc:
        logging.error("Another bot instance is already polling this token: %s", exc)
    finally:
        try:
            if app.updater:
                await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception as exc:
            logging.warning("Error during bot shutdown: %s", exc)


def main() -> None:
    ensure_project_root()
    ensure_env_loaded()
    try:
        with bot_instance_lock():
            asyncio.run(_run_polling())
    except RuntimeError as exc:
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
