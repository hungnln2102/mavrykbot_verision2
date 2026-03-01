"""
Gọi API Website: notify-done, cancel, danh sách NCC (suppliers).
Đọc NOTIFY_ORDER_BASE_URL và NOTIFY_ORDER_API_KEY khi gọi (sau khi .env đã load).
Luôn dùng HTTP cho 127.0.0.1/localhost để tránh SSL WRONG_VERSION_NUMBER.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Tuple
from urllib.parse import urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
REQUEST_VERIFY = True
LOCALHOST_NAMES = ("127.0.0.1", "localhost", "::1")


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
    """
    base = os.getenv("NOTIFY_ORDER_BASE_URL") or ""
    key = (os.getenv("NOTIFY_ORDER_API_KEY") or "").strip()
    base = _normalize_base_url(base)
    # Trên production server: nếu base đang là localhost mà có NOTIFY_ORDER_BASE_URL_PRODUCTION thì dùng production URL
    try:
        p = urlparse(base)
        if (p.hostname or "").lower() in LOCALHOST_NAMES:
            prod_base = (os.getenv("NOTIFY_ORDER_BASE_URL_PRODUCTION") or "").strip().rstrip("/")
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
        return False, "Chưa cấu hình NOTIFY_ORDER_BASE_URL / NOTIFY_ORDER_API_KEY"
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
    base, key = get_notify_order_config()
    if not base or not key:
        return False, [], "Chưa cấu hình NOTIFY_ORDER_BASE_URL / NOTIFY_ORDER_API_KEY"
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
