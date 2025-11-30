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
    try:
        await app.updater.start_polling()
        await app.updater.idle()
    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
