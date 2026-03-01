"""
Gọi API Website: notify-done, cancel, danh sách NCC (suppliers).
Đọc NOTIFY_ORDER_BASE_URL và NOTIFY_ORDER_API_KEY khi gọi (sau khi .env đã load).
Dùng requests để tránh lỗi SSL/redirect khi gọi HTTPS.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Tuple

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
REQUEST_VERIFY = True


def get_notify_order_config() -> Tuple[str, str]:
    """Đọc cấu hình khi gọi (sau khi .env đã load)."""
    base = (os.getenv("NOTIFY_ORDER_BASE_URL") or "").rstrip("/")
    key = (os.getenv("NOTIFY_ORDER_API_KEY") or "").strip()
    return base, key


def call_order_api(path: str, body: dict) -> Tuple[bool, str]:
    """POST tới API orders (notify-done, cancel). Trả về (success, message)."""
    base, key = get_notify_order_config()
    if not base or not key:
        return False, "Chưa cấu hình NOTIFY_ORDER_BASE_URL / NOTIFY_ORDER_API_KEY"
    url = f"{base}{path}"
    try:
        r = requests.post(
            url,
            json=body,
            headers={"Content-Type": "application/json", "X-Api-Key": key},
            timeout=REQUEST_TIMEOUT,
            verify=REQUEST_VERIFY,
            allow_redirects=True,
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
        logger.warning("Order API SSL error (check NOTIFY_ORDER_BASE_URL scheme): %s", e)
        return False, str(e)
    except requests.exceptions.RequestException as e:
        logger.exception("Order API call failed")
        return False, str(e)


def get_suppliers() -> Tuple[bool, list, str]:
    """GET /api/orders/suppliers. Trả về (ok, list of {id, supplier_name}, error_msg)."""
    base, key = get_notify_order_config()
    if not base or not key:
        return False, [], "Chưa cấu hình NOTIFY_ORDER_BASE_URL / NOTIFY_ORDER_API_KEY"
    if base.rstrip("/").endswith("/api"):
        url = f"{base.rstrip('/')}/orders/suppliers"
    else:
        url = f"{base}/api/orders/suppliers"
    try:
        r = requests.get(
            url,
            headers={"X-Api-Key": key},
            timeout=REQUEST_TIMEOUT,
            verify=REQUEST_VERIFY,
            allow_redirects=True,
        )
        raw = r.text
        if r.status_code == 404:
            return False, [], (
                f"GET {url} trả về 404. Kiểm tra NOTIFY_ORDER_BASE_URL "
                "và đảm bảo server Website đã deploy route GET /api/orders/suppliers."
            )
        try:
            out = r.json()
            if out.get("success") and "suppliers" in out:
                return True, out["suppliers"], ""
            return False, [], out.get("error", raw)
        except json.JSONDecodeError:
            return False, [], raw
    except requests.exceptions.SSLError as e:
        logger.warning("getSuppliers SSL error (check NOTIFY_ORDER_BASE_URL use https vs http): %s", e)
        return False, [], str(e)
    except requests.exceptions.RequestException as e:
        logger.exception("getSuppliers failed")
        return False, [], str(e)
