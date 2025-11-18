from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


def _find_env_file() -> Path | None:
    """
    Search upwards from this module for the first .env file.
    This keeps local development flexible regardless of where the script runs.
    """
    current = Path(__file__).resolve()
    for directory in (current.parent, *current.parents):
        env_candidate = directory / ".env"
        if env_candidate.exists():
            return env_candidate
    return None


ENV_PATH = _find_env_file()


def _load_env_file() -> None:
    if not ENV_PATH:
        return

    with ENV_PATH.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


@dataclass(frozen=True)
class BotConfig:
    token: str


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


def load_bot_config() -> BotConfig:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment or .env file.")
    return BotConfig(token=token)


def load_database_config() -> DatabaseConfig:
    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "3306"))
    name = os.environ.get("DB_NAME", "mavrykstore")
    user = os.environ.get("DB_USER", "root")
    password = os.environ.get("DB_PASSWORD", "")
    return DatabaseConfig(host=host, port=port, name=name, user=user, password=password)

@dataclass(frozen=True)
class SepayConfig:
    """Cấu hình cho dịch vụ thanh toán Sepay."""
    base_url: str
    api_key: str
    webhook_secret: str

def load_sepay_config() -> SepayConfig:
    """Tải cấu hình Sepay từ biến môi trường."""
    # Giả định các biến này đã được đặt trong file .env
    base_url = os.environ.get("SEPAY_BASE_URL", "https://api.sepay.vn/")
    api_key = os.environ.get("SEPAY_API_KEY")
    webhook_secret = os.environ.get("SEPAY_WEBHOOK_SECRET")
    
    if not api_key:
        raise RuntimeError("Missing SEPAY_API_KEY in environment or .env file.")
    # Webhook secret là quan trọng để xác minh, nên kiểm tra nó
    if not webhook_secret:
        raise RuntimeError("Missing SEPAY_WEBHOOK_SECRET in environment or .env file.")
        
    return SepayConfig(base_url=base_url, api_key=api_key, webhook_secret=webhook_secret)
