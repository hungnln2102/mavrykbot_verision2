"""Cấu hình bot – chỉ token (menu-only bot)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _find_env_file() -> Path | None:
    current = Path(__file__).resolve()
    for directory in (current.parent, *current.parents):
        env_candidate = directory / ".env"
        if env_candidate.exists():
            return env_candidate
    return None


def _load_env_file() -> None:
    env_path = _find_env_file()
    if not env_path:
        return
    with env_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


@dataclass(frozen=True)
class BotConfig:
    token: str


def load_bot_config() -> BotConfig:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment or .env file.")
    return BotConfig(token=token)
