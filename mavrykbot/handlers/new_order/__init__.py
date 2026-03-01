"""
New Order: luồng Hoàn thành / Hủy đơn từ thông báo đơn hàng mới.
Toàn bộ module chỉ sử dụng topic New Order (message_thread_id từ tin nhắn đơn hoặc NEW_ORDER_TOPIC_ID).
Đăng ký callback + message handler vào Application.
"""
from __future__ import annotations

import re
from typing import Callable

from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from mavrykbot.handlers.new_order.callbacks import new_order_callback
from mavrykbot.handlers.new_order.message import order_done_text_handler


# Chỉ xử lý callback_data từ nút Hoàn thành / Hủy Đơn / Chọn NCC
NEW_ORDER_CALLBACK_PATTERN = re.compile(
    r"^(order_done:.+|order_cancel:.+|done_supply:.+|done_cancel)$"
)


def register_new_order_handlers(
    application: Application,
    user_only_filter: Callable[..., object],
) -> None:
    """
    Đăng ký handlers cho New Order vào application.
    Gọi từ main.build_application() sau khi có user_only_filter.
    """
    wrapped_callback = user_only_filter(new_order_callback)
    wrapped_text_handler = user_only_filter(order_done_text_handler)

    application.add_handler(
        CallbackQueryHandler(wrapped_callback, pattern=NEW_ORDER_CALLBACK_PATTERN),
        group=0,
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, wrapped_text_handler),
    )


__all__ = [
    "register_new_order_handlers",
    "order_done_text_handler",
    "new_order_callback",
]
