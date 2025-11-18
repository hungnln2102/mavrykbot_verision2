from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import ORDER_LIST_TABLE, OrderListColumns
from mavrykbot.core.utils import escape_mdv2
from mavrykbot.handlers.menu import show_outer_menu

logger = logging.getLogger(__name__)

(
    BROWSING,
) = range(1)

UNPAID_CACHE_KEY = "unpaid_orders"
UNPAID_INDEX_KEY = "unpaid_index"
TARGET_STATUS = "Chưa Thanh Toán"
MAX_UNPAID_RESULTS = 100


@dataclass
class UnpaidOrder:
    db_id: int
    order_code: str
    product_name: str
    description: str
    customer_name: str
    customer_link: str
    slot: str
    start_date: Optional[date]
    duration_text: str
    expiry_date: Optional[date]
    sale_price: Optional[int]
    note: str
    days_left: int


def _coerce_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    value_str = str(value).strip()
    if not value_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue
    return None


def _coerce_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _format_date(value: Optional[date]) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _format_currency(amount: Optional[int]) -> str:
    if amount is None:
        return "Chưa cập nhật"
    return f"{amount:,} đ"


def _build_keyboard(order_code: str, index: int, total: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if index > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data="prev_unpaid"))
    if index < total - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data="next_unpaid"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton("✅ Đã Thanh Toán", callback_data=f"paid_unpaid|{order_code}"),
            InlineKeyboardButton("🗑️ Xóa đơn", callback_data=f"delete_unpaid|{order_code}"),
        ]
    )
    rows.append([InlineKeyboardButton("🔚 Kết thúc", callback_data="exit_unpaid")])
    return InlineKeyboardMarkup(rows)


def fetch_unpaid_orders(limit: int = MAX_UNPAID_RESULTS) -> OrderedDict[str, UnpaidOrder]:
    sql = f"""
        SELECT
            {OrderListColumns.ID},
            {OrderListColumns.ID_DON_HANG},
            {OrderListColumns.SAN_PHAM},
            {OrderListColumns.THONG_TIN_SAN_PHAM},
            {OrderListColumns.KHACH_HANG},
            {OrderListColumns.LINK_LIEN_HE},
            {OrderListColumns.SLOT},
            {OrderListColumns.NGAY_DANG_KI},
            {OrderListColumns.SO_NGAY_DA_DANG_KI},
            {OrderListColumns.HET_HAN},
            {OrderListColumns.GIA_BAN},
            {OrderListColumns.NOTE}
        FROM {ORDER_LIST_TABLE}
        WHERE
            COALESCE(TRIM({OrderListColumns.CHECK_FLAG}::text), '') = ''
            AND LOWER({OrderListColumns.TINH_TRANG}) = LOWER(%s)
        ORDER BY {OrderListColumns.NGAY_DANG_KI} DESC, {OrderListColumns.ID} DESC
        LIMIT %s
    """
    rows = db.fetch_all(sql, (TARGET_STATUS, limit))
    orders: OrderedDict[str, UnpaidOrder] = OrderedDict()
    today = date.today()
    for row in rows:
        (
            db_id,
            order_code,
            product_name,
            description,
            customer_name,
            customer_link,
            slot,
            start_date_raw,
            duration_raw,
            expiry_date_raw,
            price_raw,
            note,
        ) = row
        code = (order_code or "").strip()
        if not code:
            continue
        expiry_date = _coerce_date(expiry_date_raw)
        days_left = (expiry_date - today).days if expiry_date else 0
        orders[code] = UnpaidOrder(
            db_id=db_id,
            order_code=code,
            product_name=(product_name or "").strip(),
            description=(description or "").strip(),
            customer_name=(customer_name or "").strip(),
            customer_link=(customer_link or "").strip(),
            slot=(slot or "").strip(),
            start_date=_coerce_date(start_date_raw),
            duration_text=str(duration_raw).strip() if duration_raw not in (None, "") else "",
            expiry_date=expiry_date,
            sale_price=_coerce_int(price_raw),
            note=(note or "").strip(),
            days_left=days_left,
        )
    return orders


def build_order_text(order: UnpaidOrder, index: int, total: int) -> str:
    ma_don = escape_mdv2(order.order_code)
    product = escape_mdv2(order.product_name or "Chưa cập nhật")
    description = escape_mdv2(order.description or "Không có mô tả")
    customer = escape_mdv2(order.customer_name or "Khách")
    customer_link = escape_mdv2(order.customer_link or "")
    slot = escape_mdv2(order.slot or "")
    ngay_dang_ky = escape_mdv2(_format_date(order.start_date))
    duration = escape_mdv2(order.duration_text or "N/A")
    expiry = escape_mdv2(_format_date(order.expiry_date))
    gia_ban = escape_mdv2(_format_currency(order.sale_price))
    days_left = escape_mdv2(str(order.days_left))
    note = escape_mdv2(order.note) if order.note else ""

    parts = [
        f"📋 *Đơn hàng chưa thanh toán* `({index + 1}/{total})`",
        f"*Mã đơn:* {ma_don}",
        "",
        "📦 *THÔNG TIN SẢN PHẨM*",
        f"🔸 *Tên:* {product}",
        f"📝 *Mô tả:* {description}",
    ]
    if slot:
        parts.append(f"🎯 *Slot:* {slot}")
    if ngay_dang_ky:
        parts.append(f"📅 Ngày đăng ký: {ngay_dang_ky}")
    parts.append(f"⏳ *Thời hạn:* {duration} ngày")
    if expiry:
        parts.append(f"📆 Ngày hết hạn: {expiry}")
    parts.extend(
        [
            f"💰 *Giá bán:* {gia_ban}",
            "",
            "━━━━━━━━━━━ 👤 ━━━━━━━━━━━",
            "👥 *THÔNG TIN KHÁCH HÀNG*",
            f"🙍 *Tên:* {customer}",
        ]
    )
    if customer_link:
        parts.append(f"🔗 *Liên hệ:* {customer_link}")
    parts.append(f"⏱️ *Còn lại:* {days_left} ngày")
    if note:
        parts.append(f"🗒️ *Ghi chú:* {note}")
    return "\n".join(parts)


def _cleanup_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(UNPAID_CACHE_KEY, None)
    context.user_data.pop(UNPAID_INDEX_KEY, None)


async def _render_current_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    direction: str = "stay",
    answered: bool = False,
) -> int:
    query = update.callback_query
    if query and not answered:
        await query.answer()

    orders: OrderedDict[str, UnpaidOrder] = context.user_data.get(UNPAID_CACHE_KEY, OrderedDict())
    if not orders:
        if query:
            await query.edit_message_text("🎉 Tuyệt vời! Không còn đơn chưa thanh toán.")
        elif update.effective_message:
            await update.effective_message.reply_text("🎉 Tuyệt vời! Không còn đơn chưa thanh toán.")
        _cleanup_context(context)
        return ConversationHandler.END

    keys = list(orders.keys())
    if not keys:
        if query:
            await query.edit_message_text("🎉 Tuyệt vời! Không còn đơn chưa thanh toán.")
        elif update.effective_message:
            await update.effective_message.reply_text("🎉 Tuyệt vời! Không còn đơn chưa thanh toán.")
        _cleanup_context(context)
        return ConversationHandler.END

    index = context.user_data.get(UNPAID_INDEX_KEY, 0)
    if direction == "next":
        index = min(index + 1, len(keys) - 1)
    elif direction == "prev":
        index = max(index - 1, 0)
    else:
        index = max(0, min(index, len(keys) - 1))
    context.user_data[UNPAID_INDEX_KEY] = index

    order = orders[keys[index]]
    text = build_order_text(order, index, len(keys))
    keyboard = _build_keyboard(order.order_code, index, len(keys))

    if query:
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.effective_chat.send_message(
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    return BROWSING


async def start_unpaid_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer("Đang tải dữ liệu...")
    try:
        orders = fetch_unpaid_orders()
    except Exception as exc:
        logger.error("Không thể tải đơn chưa thanh toán: %s", exc, exc_info=True)
        message = "⚠️ Lỗi khi lấy dữ liệu đơn hàng."
        if query:
            await query.edit_message_text(message)
        elif update.effective_message:
            await update.effective_message.reply_text(message)
        return ConversationHandler.END

    if not orders:
        message = "🎉 Tuyệt vời! Không có đơn hàng nào chưa thanh toán."
        if query:
            await query.edit_message_text(message)
        elif update.effective_message:
            await update.effective_message.reply_text(message)
        return ConversationHandler.END

    context.user_data[UNPAID_CACHE_KEY] = orders
    context.user_data[UNPAID_INDEX_KEY] = 0
    return await _render_current_order(update, context, answered=bool(query))


async def show_unpaid_order(
    update: Update, context: ContextTypes.DEFAULT_TYPE, direction: str, *, answered: bool = False
) -> int:
    return await _render_current_order(update, context, direction=direction, answered=answered)


def _delete_order_from_db(order: UnpaidOrder) -> None:
    sql = f"DELETE FROM {ORDER_LIST_TABLE} WHERE {OrderListColumns.ID} = %s"
    db.execute(sql, (order.db_id,))


def _mark_order_paid_in_db(order: UnpaidOrder) -> None:
    sql = f"""
        UPDATE {ORDER_LIST_TABLE}
        SET
            {OrderListColumns.CHECK_FLAG} = 'True',
            {OrderListColumns.TINH_TRANG} = %s
        WHERE {OrderListColumns.ID} = %s
    """
    db.execute(sql, ("Đã Thanh Toán", order.db_id))


async def handle_action_and_update_view(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ma_don: str,
    action_type: str,
) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    orders: OrderedDict[str, UnpaidOrder] = context.user_data.get(UNPAID_CACHE_KEY, OrderedDict())
    order = orders.get(ma_don)
    if not order:
        if query:
            await query.answer("Không tìm thấy đơn trong bộ nhớ.", show_alert=True)
        return BROWSING

    try:
        if action_type == "delete":
            _delete_order_from_db(order)
        else:
            _mark_order_paid_in_db(order)
    except Exception as exc:
        logger.error("Lỗi khi cập nhật đơn %s (%s): %s", ma_don, action_type, exc, exc_info=True)
        if query:
            await query.answer("Không thể cập nhật database.", show_alert=True)
        return BROWSING

    orders.pop(ma_don, None)
    if not orders:
        if query:
            await query.edit_message_text("🎉 Tuyệt vời! Đã xử lý xong tất cả đơn chưa thanh toán.")
        _cleanup_context(context)
        return ConversationHandler.END

    current_index = context.user_data.get(UNPAID_INDEX_KEY, 0)
    context.user_data[UNPAID_INDEX_KEY] = min(current_index, len(orders) - 1)
    return await show_unpaid_order(update, context, "stay", answered=True)


async def delete_unpaid_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ma_don = update.callback_query.data.split("|", 1)[1].strip()
    return await handle_action_and_update_view(update, context, ma_don, "delete")


async def mark_paid_unpaid_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ma_don = update.callback_query.data.split("|", 1)[1].strip()
    return await handle_action_and_update_view(update, context, ma_don, "mark_paid")


async def exit_unpaid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer("Đã thoát.")
    _cleanup_context(context)
    await show_outer_menu(update, context)
    return ConversationHandler.END


def get_unpaid_order_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_unpaid_orders, pattern="^unpaid_orders$"),
            CommandHandler("unpaid", start_unpaid_orders),
        ],
        states={
            BROWSING: [
                CallbackQueryHandler(
                    lambda u, c: show_unpaid_order(u, c, "prev"), pattern="^prev_unpaid$"
                ),
                CallbackQueryHandler(
                    lambda u, c: show_unpaid_order(u, c, "next"), pattern="^next_unpaid$"
                ),
                CallbackQueryHandler(mark_paid_unpaid_order, pattern="^paid_unpaid\\|"),
                CallbackQueryHandler(delete_unpaid_order, pattern="^delete_unpaid\\|"),
                CallbackQueryHandler(exit_unpaid, pattern="^exit_unpaid$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(exit_unpaid, pattern="^exit_unpaid$"),
            CommandHandler("cancel", exit_unpaid),
        ],
        name="view_unpaid_orders",
        persistent=False,
        allow_reentry=True,
    )
