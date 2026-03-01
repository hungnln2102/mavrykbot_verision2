"""
Gọi API Website: notify-done, cancel, danh sách NCC (suppliers).
Đọc NOTIFY_ORDER_BASE_URL và NOTIFY_ORDER_API_KEY khi gọi (sau khi .env đã load).
Luôn dùng HTTP cho 127.0.0.1/localhost để tránh SSL WRONG_VERSION_NUMBER.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Tuple
from urllib.parse import urlparse, urlunparse

import requests

from mavrykbot.bootstrap import get_env_path

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
REQUEST_VERIFY = True
LOCALHOST_NAMES = ("127.0.0.1", "localhost", "::1")


def _pick_one_base_url(raw: str, prefer_https: bool = False) -> str:
    """Từ chuỗi có thể chứa nhiều URL (cách nhau bằng dấu phẩy), trả về một URL hợp lệ.
    prefer_https: nếu True thì ưu tiên segment bắt đầu bằng https (cho production).
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if prefer_https:
        for p in parts:
            if p.lower().startswith("https://"):
                parsed = urlparse(p)
                if parsed.hostname:
                    return p.strip().rstrip("/")
        for p in parts:
            if p.lower().startswith("http://"):
                parsed = urlparse(p)
                if parsed.hostname:
                    return p.strip().rstrip("/")
        return ""
    for p in parts:
        parsed = urlparse(p)
        if parsed.hostname:
            return p.strip().rstrip("/")
    return ""


def _ensure_single_base(base: str) -> str:
    """Đảm bảo base là một URL hợp lệ, không chứa dấu phẩy (phòng env ghi nhầm nhiều URL)."""
    base = (base or "").strip()
    if "," not in base:
        return base.rstrip("/")
    fixed = _pick_one_base_url(base, prefer_https=True) or _pick_one_base_url(base)
    if fixed:
        logger.warning("NOTIFY_ORDER_BASE_URL chứa dấu phẩy, đã dùng một URL: %s", fixed)
        return fixed.rstrip("/")
    return base.rstrip("/")


def _normalize_base_url(base: str) -> str:
    """Ép http cho host local để tránh SSL lỗi (kể cả khi env ghi https)."""
    base = (base or "").strip().rstrip("/")
    if not base:
        return base
    try:
        p = urlparse(base)
        host = (p.hostname or "").lower()
        # Luôn dùng http cho localhost (tránh WRONG_VERSION_NUMBER khi server chỉ lắng HTTP)
        if host in LOCALHOST_NAMES and p.scheme.lower() != "http":
            base = urlunparse(("http", p.netloc, p.path or "", p.params, p.query, p.fragment))
            logger.info("NOTIFY_ORDER_BASE_URL: localhost ép dùng http")
    except Exception:
        pass
    return base


def _request_kw(base: str) -> dict:
    """verify=False cho localhost; allow_redirects=False cho localhost để không follow redirect lên HTTPS (tránh SSL)."""
    try:
        p = urlparse(base)
        if (p.hostname or "").lower() in LOCALHOST_NAMES:
            return {
                "verify": False,
                "timeout": REQUEST_TIMEOUT,
                "allow_redirects": False,  # tránh follow 301/302 → https gây SSLError
            }
    except Exception:
        pass
    return {"verify": REQUEST_VERIFY, "timeout": REQUEST_TIMEOUT, "allow_redirects": True}


def get_notify_order_config() -> Tuple[str, str]:
    """Đọc cấu hình khi gọi (sau khi .env đã load).
    Production: set NOTIFY_ORDER_BASE_URL_PRODUCTION=https://api.mavrykpremium.store để gọi API thật, không dùng 127.0.0.1.
    Nếu giá trị env chứa nhiều URL (cách nhau bằng dấu phẩy), chỉ lấy một URL hợp lệ.
    """
    raw_base = os.getenv("NOTIFY_ORDER_BASE_URL") or ""
    base = _pick_one_base_url(raw_base)
    if not base and "," in raw_base:
        logger.warning("NOTIFY_ORDER_BASE_URL có dấu phẩy, chỉ nên set một URL: %s", raw_base[:80])
    key = (os.getenv("NOTIFY_ORDER_API_KEY") or "").strip()
    logger.info("get_notify_order_config: NOTIFY_ORDER_API_KEY len=%s", len(key))
    # Nếu thiếu key, thử load lại .env với override=True rồi fallback đọc trực tiếp từ file
    if not key:
        try:
            from dotenv import load_dotenv
            env_path = get_env_path()
            if env_path.exists():
                load_dotenv(env_path, override=True)
                key = (os.getenv("NOTIFY_ORDER_API_KEY") or "").strip()
            if not key and env_path.exists():
                # Fallback: đọc trực tiếp dòng NOTIFY_ORDER_API_KEY= trong file
                with open(env_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or not line.startswith("NOTIFY_ORDER_API_KEY="):
                            continue
                        key = line.split("=", 1)[1].strip().strip("'\"").strip()
                        if key:
                            os.environ["NOTIFY_ORDER_API_KEY"] = key
                            logger.info("NOTIFY_ORDER_API_KEY đọc từ file .env (fallback)")
                        break
            if not key:
                msg = (
                    f"NOTIFY_ORDER_API_KEY trống. Kiểm tra file .env tại: {env_path.resolve()} "
                    "(phải có dòng NOTIFY_ORDER_API_KEY=...)"
                )
                logger.warning("%s", msg)
                print(f"[MAVRYKBOT ERROR] {msg}", file=sys.stderr, flush=True)
        except Exception as e:
            logger.warning("Không load lại .env được: %s", e)
            print(f"[MAVRYKBOT ERROR] load_dotenv: {e}", file=sys.stderr, flush=True)
    base = _normalize_base_url(base)
    # Trên production server: nếu base đang là localhost mà có NOTIFY_ORDER_BASE_URL_PRODUCTION thì dùng production URL
    try:
        p = urlparse(base)
        if (p.hostname or "").lower() in LOCALHOST_NAMES:
            raw_prod = os.getenv("NOTIFY_ORDER_BASE_URL_PRODUCTION") or ""
            prod_base = _pick_one_base_url(raw_prod, prefer_https=True)
            if prod_base:
                base = _normalize_base_url(prod_base)
                logger.info("NOTIFY_ORDER_BASE_URL_PRODUCTION được dùng thay cho localhost")
    except Exception:
        pass
    return base, key


def call_order_api(path: str, body: dict) -> Tuple[bool, str]:
    """POST tới API orders (notify-done, cancel). Trả về (success, message)."""
    base, key = get_notify_order_config()
    if not base or not key:
        env_path = get_env_path().resolve()
        return False, (
            f"NOTIFY_ORDER_API_KEY chưa cấu hình. Kiểm tra file .env tại: {env_path}"
        )
    base = _ensure_single_base(base)
    url = base.rstrip("/") + (path if path.startswith("/") else "/" + path)
    kw = _request_kw(base)
    try:
        r = requests.post(
            url,
            json=body,
            headers={"Content-Type": "application/json", "X-Api-Key": key},
            **kw,
        )
        raw = r.text
        try:
            out = r.json()
            if out.get("success"):
                return True, "OK"
            return False, out.get("error") or raw
        except json.JSONDecodeError:
            return (r.status_code == 200, raw)
    except requests.exceptions.SSLError as e:
        logger.warning("Order API SSL error (NOTIFY_ORDER_BASE_URL nên dùng http cho local): %s", e)
        return False, str(e)
    except requests.exceptions.RequestException as e:
        logger.exception("Order API call failed")
        return False, str(e)


def get_suppliers() -> Tuple[bool, list, str]:
    """GET /api/orders/suppliers. Trả về (ok, list of {id, supplier_name}, error_msg)."""
    logger.info("get_suppliers called")
    base, key = get_notify_order_config()
    if not base or not key:
        env_path = get_env_path().resolve()
        err = (
            "NOTIFY_ORDER_API_KEY chưa cấu hình. Thêm vào file .env tại: "
            f"{env_path} (dòng: NOTIFY_ORDER_API_KEY=giá_trị_cùng_server_Website)"
        )
        logger.error("get_suppliers: %s", err)
        print(f"[MAVRYKBOT ERROR] get_suppliers: {err}", file=sys.stderr, flush=True)
        return False, [], err
    base = _ensure_single_base(base)
    base_clean = base.rstrip("/")
    if base_clean.endswith("/api"):
        url = f"{base_clean}/orders/suppliers"
    else:
        url = f"{base_clean}/api/orders/suppliers"
    kw = _request_kw(base)
    try:
        r = requests.get(
            url,
            headers={"X-Api-Key": key},
            **kw,
        )
        raw = r.text
        if r.status_code == 404:
            return False, [], (
                f"GET {url} trả về 404. Kiểm tra NOTIFY_ORDER_BASE_URL "
                "và đảm bảo server Website đã deploy route GET /api/orders/suppliers."
            )
        if r.status_code == 301:
            return False, [], (
                "API trả về 301 (Moved Permanently). Trên production hãy set "
                "NOTIFY_ORDER_BASE_URL_PRODUCTION=https://api.mavrykpremium.store trong .env của bot (hoặc đổi NOTIFY_ORDER_BASE_URL sang URL production)."
            )
        try:
            out = r.json()
            if out.get("success") and "suppliers" in out:
                return True, out["suppliers"], ""
            return False, [], out.get("error", raw)
        except json.JSONDecodeError:
            return False, [], raw
    except requests.exceptions.SSLError as e:
        logger.warning("getSuppliers SSL (NOTIFY_ORDER_BASE_URL dùng http cho local): %s", e)
        return False, [], str(e)
    except requests.exceptions.RequestException as e:
        logger.exception("getSuppliers failed")
        return False, [], str(e)
