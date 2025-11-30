from __future__ import annotations

import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:  # fcntl is available on Unix-like systems
    import fcntl
except ImportError:  # pragma: no cover - platform specific
    fcntl = None

try:  # msvcrt is available on Windows
    import msvcrt
except ImportError:  # pragma: no cover - platform specific
    msvcrt = None

logger = logging.getLogger(__name__)
DEFAULT_LOCK_NAME = "mavrykbot_polling.lock"


@contextmanager
def bot_instance_lock(lock_name: str = DEFAULT_LOCK_NAME):
    """
    Cross-platform file lock to ensure only one bot process runs per host.

    On Linux it uses fcntl.flock; on Windows it falls back to msvcrt.locking.
    If locking fails, a RuntimeError is raised so the caller can exit gracefully.
    """
    lock_path = Path(tempfile.gettempdir()) / lock_name
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+")
    try:
        if fcntl:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif msvcrt:
            # Ensure the file is at least one byte for Windows locking.
            lock_file.seek(0)
            lock_file.write("0")
            lock_file.flush()
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - defensive guard
            raise RuntimeError("File locking is not available on this platform.")

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        yield lock_path
    except (BlockingIOError, OSError):
        raise RuntimeError(f"Another bot instance is already running (lock: {lock_path}).")
    finally:
        try:
            if fcntl:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
            elif msvcrt:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            lock_file.close()
            lock_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.debug("Failed to release bot lock %s", lock_path, exc_info=True)
