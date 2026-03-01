"""
Gọi API Website: notify-done, cancel, danh sách NCC (suppliers).
Đọc NOTIFY_ORDER_BASE_URL và NOTIFY_ORDER_API_KEY khi gọi (sau khi .env đã load).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Tuple

logger = logging.getLogger(__name__)


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
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-Api-Key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            try:
                out = json.loads(raw)
                if out.get("success"):
                    return True, "OK"
                return False, out.get("error") or raw
            except json.JSONDecodeError:
                return (resp.status == 200, raw)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            j = json.loads(err_body)
            return False, j.get("error", err_body)
        except Exception:
            return False, str(e)
    except Exception as e:
        logger.exception("Order API call failed")
        return False, str(e)


def get_suppliers() -> Tuple[bool, list, str]:
    """GET /api/orders/suppliers. Trả về (ok, list of {id, supplier_name}, error_msg)."""
    base, key = get_notify_order_config()
    if not base or not key:
        return False, [], "Chưa cấu hình NOTIFY_ORDER_BASE_URL / NOTIFY_ORDER_API_KEY"
    # Hỗ trợ base có hoặc không có /api (vd. https://api.x.com hoặc https://api.x.com/api)
    if base.rstrip("/").endswith("/api"):
        url = f"{base.rstrip('/')}/orders/suppliers"
    else:
        url = f"{base}/api/orders/suppliers"
    req = urllib.request.Request(
        url,
        headers={"X-Api-Key": key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            out = json.loads(raw)
            if out.get("success") and "suppliers" in out:
                return True, out["suppliers"], ""
            return False, [], out.get("error", raw)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, [], (
                f"GET {url} trả về 404. Kiểm tra NOTIFY_ORDER_BASE_URL (chỉ gốc, vd. https://api.mavrykpremium.store) "
                "và đảm bảo server Website đã deploy route GET /api/orders/suppliers."
            )
        try:
            err_body = e.read().decode("utf-8")
            j = json.loads(err_body)
            return False, [], j.get("error", err_body)
        except Exception:
            return False, [], str(e)
    except Exception as e:
        logger.exception("getSuppliers failed")
        return False, [], str(e)
