from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
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


@dataclass(frozen=True)
class TopicConfig:
    send_renewal_to_topic: bool
    renewal_group_id: str | None
    renewal_topic_id: int | None
    send_error_to_topic: bool
    error_group_id: str | None
    error_topic_id: int | None
    send_due_order_to_topic: bool
    due_order_group_id: str | None
    due_order_topic_id: int | None


def _env_bool(var_name: str, default: bool) -> bool:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y"}


def _env_int(var_name: str, default: int | None) -> int | None:
    raw = os.environ.get(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


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


@lru_cache(maxsize=1)
def load_topic_config() -> TopicConfig:
    default_group = "-1002934465528"
    return TopicConfig(
        send_renewal_to_topic=_env_bool("SEND_RENEWAL_TO_TOPIC", True),
        renewal_group_id=os.environ.get("RENEWAL_GROUP_ID") or default_group,
        renewal_topic_id=_env_int("RENEWAL_TOPIC_ID", 2),
        send_error_to_topic=_env_bool("SEND_ERROR_TO_TOPIC", True),
        error_group_id=os.environ.get("ERROR_GROUP_ID") or default_group,
        error_topic_id=_env_int("ERROR_TOPIC_ID", 6),
        send_due_order_to_topic=_env_bool("SEND_DUE_ORDER_TO_TOPIC", True),
        due_order_group_id=os.environ.get("DUE_ORDER_GROUP_ID") or default_group,
        due_order_topic_id=_env_int("DUE_ORDER_TOPIC_ID", 12),
    )

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
