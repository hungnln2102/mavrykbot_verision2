"""Entry point to run the Telegram bot (polling mode)."""
from __future__ import annotations

import logging

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root
from mavrykbot.handlers.main import build_application


def main() -> None:
    ensure_project_root()
    ensure_env_loaded()

    app = build_application()
    logging.info("Starting Telegram bot in polling mode...")
    # run_polling handles init/start/stop/shutdown internally (blocking)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
