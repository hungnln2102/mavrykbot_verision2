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


def _skip_bot_lock() -> bool:
    """Return True if SKIP_BOT_LOCK env var is set to skip the file lock."""
    return os.environ.get("SKIP_BOT_LOCK", "").strip().lower() in ("1", "true", "yes")


def _is_process_running(pid: int) -> bool:
    """Return True if a process with the given PID is running (cross-platform)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError as e:
        # errno 3 = ESRCH (no such process); 87 on Windows
        if getattr(e, "errno", None) in (3, 87):
            return False
        return True
    return True


def _remove_stale_lock(lock_path: Path) -> None:
    """If lock file exists and the PID in it is no longer running, remove it."""
    if not lock_path.exists():
        return
    try:
        raw = lock_path.read_text().strip()
        pid = int(raw)
    except (ValueError, OSError):
        pid = None
    if pid is None:
        try:
            lock_path.unlink(missing_ok=True)
            logger.info("Removed invalid lock file %s", lock_path)
        except OSError:
            pass
        return
    if not _is_process_running(pid):
        try:
            lock_path.unlink(missing_ok=True)
            logger.info("Removed stale lock file %s (PID %s no longer running)", lock_path, pid)
        except OSError:
            pass


@contextmanager
def bot_instance_lock(lock_name: str = DEFAULT_LOCK_NAME):
    """
    Cross-platform file lock to ensure only one bot process runs per host.

    On Linux it uses fcntl.flock; on Windows it falls back to msvcrt.locking.
    If locking fails, a RuntimeError is raised so the caller can exit gracefully.
    Set SKIP_BOT_LOCK=1 (or true/yes) to disable the lock and allow multiple instances.
    """
    lock_path = Path(tempfile.gettempdir()) / lock_name
    if _skip_bot_lock():
        yield lock_path
        return

    _remove_stale_lock(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+")
    locked = False
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

        locked = True
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        yield lock_path
    except (BlockingIOError, OSError):
        pid_str = "?"
        try:
            lock_file.seek(0)
            pid_str = (lock_file.read().strip() or "?")[:20]
        except Exception:
            pass
        try:
            lock_file.close()
        except Exception:
            pass
        hint = ""
        if pid_str not in ("", "?"):
            try:
                p = int(pid_str)
                if _is_process_running(p):
                    hint = f" Process đang chạy: PID {p}. Tắt instance đó hoặc chạy: taskkill /PID {p} /F"
            except ValueError:
                pass
        raise RuntimeError(
            f"Another bot instance is already running (lock: {lock_path}).{hint}"
        )
    finally:
        try:
            if locked:
                if fcntl:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                elif msvcrt:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                lock_file.close()
                lock_path.unlink(missing_ok=True)
            else:
                lock_file.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            logger.debug("Failed to release bot lock %s", lock_path, exc_info=True)
