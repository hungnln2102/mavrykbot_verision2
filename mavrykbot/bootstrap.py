from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_project_root() -> Path:
    """
    Ensure the repository root (folder containing `mavrykbot/`) is available on sys.path.
    Allows running modules directly from nested folders like `mavrykbot/handlers`.
    """
    root = PROJECT_ROOT
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def get_env_path(env_file: str | None = None) -> Path:
    """Đường dẫn file .env mà bot sẽ load (để kiểm tra bot đang dùng env ở đâu)."""
    return Path(env_file) if env_file else PROJECT_ROOT / ".env"


@lru_cache(maxsize=1)
def ensure_env_loaded(env_file: str | None = None) -> None:
    """
    Load environment variables once from the provided .env file (defaults to project root).
    Safe to call multiple times.
    """
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    env_path = get_env_path(env_file)
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)


def log_env_status(env_file: str | None = None) -> None:
    """
    Log đường dẫn .env đang dùng và trạng thái một số biến (không in giá trị).
    Gọi sau ensure_env_loaded() để kiểm tra bot đọc env ở đâu.
    """
    import logging
    env_path = get_env_path(env_file)
    resolved = env_path.resolve()
    exists = env_path.exists()
    cwd = os.getcwd()
    # In ra stdout để chắc chắn thấy khi chạy (kể cả trước khi logging được config)
    print(f"[ENV] path={resolved} exists={exists} cwd={cwd}")
    for key in ("TELEGRAM_BOT_TOKEN", "NOTIFY_ORDER_BASE_URL", "NOTIFY_ORDER_API_KEY", "NOTIFY_ORDER_BASE_URL_PRODUCTION"):
        val = os.getenv(key)
        status = "set" if (val and val.strip()) else "NOT SET"
        print(f"[ENV] {key}={status}")
    logger = logging.getLogger(__name__)
    logger.info(
        "ENV: path=%s exists=%s cwd=%s",
        resolved,
        exists,
        cwd,
    )
    for key in ("TELEGRAM_BOT_TOKEN", "NOTIFY_ORDER_BASE_URL", "NOTIFY_ORDER_API_KEY", "NOTIFY_ORDER_BASE_URL_PRODUCTION"):
        val = os.getenv(key)
        logger.info("ENV: %s=%s", key, "set" if (val and val.strip()) else "NOT SET")


__all__ = ["ensure_project_root", "ensure_env_loaded", "get_env_path", "log_env_status", "PROJECT_ROOT"]
