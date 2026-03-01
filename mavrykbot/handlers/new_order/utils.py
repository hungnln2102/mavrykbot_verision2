"""
Helper: mọi reply của New Order luôn gửi vào topic New Order.
Dùng message_thread_id từ tin nhắn đơn hàng, hoặc NEW_ORDER_TOPIC_ID từ .env.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def get_new_order_topic_id() -> Optional[int]:
    """Topic ID của New Order (từ .env NEW_ORDER_TOPIC_ID). Dùng khi không có thread_id từ message."""
    raw = os.getenv("NEW_ORDER_TOPIC_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def reply_in_topic_kw(thread_id: Optional[int]) -> dict[str, Any]:
    """
    Kwargs cho send_message: luôn gửi vào topic New Order.
    Ưu tiên thread_id (từ tin nhắn đơn), không có thì dùng NEW_ORDER_TOPIC_ID.
    """
    tid = thread_id if thread_id is not None else get_new_order_topic_id()
    if tid is None:
        return {}
    return {"message_thread_id": tid}
