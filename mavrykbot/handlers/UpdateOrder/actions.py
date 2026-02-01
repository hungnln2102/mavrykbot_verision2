"""Action handlers (extend, delete) for update order."""
import logging
import re
from datetime import timedelta
from decimal import Decimal
from typing import List

from telegram import Update
from telegram.ext import ContextTypes

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import ORDER_LIST_TABLE, OrderListColumns
from mavrykbot.core.utils import escape_mdv2, normalize_product_duration
from mavrykbot.handlers.Order.add_order import tinh_ngay_het_han
from mavrykbot.handlers.Order.calculate_price import calculate_sale_price
from mavrykbot.handlers.UpdateOrder.models import OrderRecord
from mavrykbot.handlers.UpdateOrder.queries import (
    lookup_highest_price,
    lookup_product_profile,
    lookup_source_price,
)
from mavrykbot.handlers.UpdateOrder.states import DATE_FMT
from mavrykbot.handlers.UpdateOrder.utils import (
    _edit_or_send_main_message,
    _find_order_by_ma,
    _round_up_to_thousand,
)

logger = logging.getLogger(__name__)


async def extend_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import end_update, show_matched_order
    
    query = update.callback_query
    await query.answer()
    ma_don = query.data.split("|", 1)[1].strip()

    matched_orders: List[OrderRecord] = context.user_data.get("matched_orders", [])
    order = _find_order_by_ma(matched_orders, ma_don)
    if not order:
        await query.answer("Không tìm thấy đơn hàng trong cache.", show_alert=True)
        return await end_update(update, context)

    san_pham_norm = normalize_product_duration(order.san_pham)
    match_thoi_han = re.search(r"--\s*(\d+)\s*m", san_pham_norm, flags=re.I)
    if not match_thoi_han:
        await query.answer("Không xác định được thời hạn trong tên sản phẩm.", show_alert=True)
        return await end_update(update, context)

    so_thang = int(match_thoi_han.group(1))
    so_ngay = 365 if so_thang == 12 else so_thang * 30

    if not order.het_han:
        await query.answer("Chưa có ngày hết hạn hiện tại.", show_alert=True)
        return await end_update(update, context)

    start_dt = order.het_han + timedelta(days=1)
    ngay_het_han_moi = tinh_ngay_het_han(start_dt.strftime(DATE_FMT), str(so_ngay))
    if not ngay_het_han_moi:
        await query.answer("Không thể tính ngày hết hạn mới.", show_alert=True)
        return await end_update(update, context)

    product_profile = lookup_product_profile(order.san_pham)
    gia_nhap_moi = order.gia_nhap or 0
    gia_ban_moi = order.gia_ban or 0

    if product_profile:
        product_id, pct_ctv_raw, pct_khach_raw, pct_promo_raw = product_profile
        pct_ctv = Decimal(str(pct_ctv_raw or 1))
        pct_khach = Decimal(str(pct_khach_raw or 1))
        pct_promo = Decimal(str(pct_promo_raw or 0))

        nguon_price = lookup_source_price(product_id, order.nguon)
        if nguon_price is not None and nguon_price > 0:
            gia_nhap_moi = nguon_price

        highest_price = lookup_highest_price(product_id)
        base_price = Decimal(highest_price) if highest_price > 0 else Decimal(gia_nhap_moi or 0)

        gia_ban_moi = calculate_sale_price(
            order.ma_don,
            base_price,
            pct_ctv=pct_ctv,
            pct_khach=pct_khach,
            pct_promo=pct_promo,
            gia_nhap=gia_nhap_moi,
        )

    gia_nhap_moi = _round_up_to_thousand(gia_nhap_moi)
    gia_ban_moi = _round_up_to_thousand(gia_ban_moi)

    try:
        db.execute(
            f"""
            UPDATE {ORDER_LIST_TABLE}
            SET {OrderListColumns.NGAY_DANG_KI} = %s,
                {OrderListColumns.SO_NGAY_DA_DANG_KI} = %s,
                {OrderListColumns.HET_HAN} = %s,
                {OrderListColumns.GIA_NHAP} = %s,
                {OrderListColumns.GIA_BAN} = %s
            WHERE {OrderListColumns.ID} = %s
            """,
            (
                start_dt,
                so_ngay,
                ngay_het_han_moi,
                gia_nhap_moi,
                gia_ban_moi,
                order.db_id,
            ),
        )
    except Exception as exc:
        logger.error("Extend order failed: %s", exc, exc_info=True)
        await query.answer("Không thể cập nhật DB.", show_alert=True)
        return await end_update(update, context)

    order.ngay_dang_ky = start_dt
    order.so_ngay = so_ngay
    order.het_han = ngay_het_han_moi
    order.gia_nhap = gia_nhap_moi
    order.gia_ban = gia_ban_moi

    await query.answer("Đã gia hạn thành công.", show_alert=True)
    return await show_matched_order(update, context)


async def delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from mavrykbot.handlers.UpdateOrder.navigation import end_update, show_matched_order
    
    query = update.callback_query
    await query.answer("Đang Xóa...")
    ma_don_to_delete = query.data.split("|", 1)[1].strip()

    matched_orders: List[OrderRecord] = context.user_data.get("matched_orders", [])
    order = _find_order_by_ma(matched_orders, ma_don_to_delete)
    if not order:
        await _edit_or_send_main_message(
            context,
            update.effective_chat.id,
            "Không Tìm Thấy Đơn Hàng.",
        )
        return await end_update(update, context)

    try:
        db.execute(
            f"DELETE FROM {ORDER_LIST_TABLE} WHERE {OrderListColumns.ID} = %s",
            (order.db_id,),
        )
    except Exception as exc:
        logger.error("Delete order failed: %s", exc, exc_info=True)
        await _edit_or_send_main_message(
            context,
            update.effective_chat.id,
            "Không Thể Xóa Đơn Hàng.",
        )
        return await end_update(update, context)

    updated = [o for o in matched_orders if o.db_id != order.db_id]
    context.user_data["matched_orders"] = updated
    if not updated:
        message = f"Đã Xóa Đơn Hàng`{escape_mdv2(ma_don_to_delete)}` Thành Công"
        await _edit_or_send_main_message(
            context,
            update.effective_chat.id,
            message,
            parse_mode="MarkdownV2",
        )
        return await end_update(update, context)

    context.user_data["current_match_index"] = 0
    return await show_matched_order(
        update, context, success_notice="Đã Xóa Đơn Hàng Thành Công."
    )
