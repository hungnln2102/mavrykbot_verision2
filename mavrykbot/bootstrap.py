from __future__ import annotations

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

    env_path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()


__all__ = ["ensure_project_root", "ensure_env_loaded", "PROJECT_ROOT"]
