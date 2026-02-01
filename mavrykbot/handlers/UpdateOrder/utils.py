"""Utility functions for update order flow."""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Sequence

from telegram import InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from mavrykbot.core.utils import (
    escape_mdv2,
    format_currency_vn,
    format_date_vn,
    parse_date,
    round_thousand,
)
from mavrykbot.handlers.UpdateOrder.models import ORDER_SELECT_FIELDS, OrderRecord
from mavrykbot.handlers.UpdateOrder.states import DATE_FMT

logger = logging.getLogger(__name__)

# Re-export consolidated utilities
_format_date = format_date_vn
_format_currency = format_currency_vn
_parse_date = parse_date
_round_up_to_thousand = round_thousand


def _today() -> date:
    return datetime.now().date()


def _parse_positive_int(value) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _remaining_days(order: OrderRecord) -> Optional[int]:
    if not order.het_han:
        return None
    return (order.het_han - _today()).days


def _remaining_value(order: OrderRecord) -> Optional[int]:
    remaining = _remaining_days(order)
    if remaining is None or order.so_ngay <= 0 or order.gia_ban <= 0:
        return None
    remaining = max(remaining, 0)
    per_day = Decimal(order.gia_ban) / Decimal(max(order.so_ngay, 1))
    return int(per_day * remaining)


def _build_order(row: Sequence) -> OrderRecord:
    return OrderRecord(
        db_id=int(row[0]),
        ma_don=str(row[1] or "").strip(),
        san_pham=str(row[2] or "").strip(),
        thong_tin=str(row[3] or "").strip(),
        ten_khach=str(row[4] or "").strip(),
        link_khach=str(row[5] or "").strip(),
        slot=str(row[6] or "").strip(),
        ngay_dang_ky=_parse_date(row[7]),
        so_ngay=_parse_positive_int(row[8]),
        het_han=_parse_date(row[9]),
        nguon=str(row[10] or "").strip(),
        gia_nhap=_parse_positive_int(row[11]),
        gia_ban=_parse_positive_int(row[12]),
        note=str(row[13] or "").strip(),
    )


def _get_active_order(context: ContextTypes.DEFAULT_TYPE) -> OrderRecord:
    matched = context.user_data.get("matched_orders") or []
    index = context.user_data.get("current_match_index", 0)
    if not matched:
        raise RuntimeError("No order selected.")
    return matched[min(max(index, 0), len(matched) - 1)]


def _find_order_by_ma(
    orders: List[OrderRecord], ma_don: str
) -> Optional[OrderRecord]:
    ma_lower = ma_don.strip().lower()
    for record in orders:
        if record.ma_don.lower() == ma_lower:
            return record
    return None


def _format_order_message(order: OrderRecord) -> str:
    ngay_dk = _format_date(order.ngay_dang_ky)
    het_han = _format_date(order.het_han)
    con_lai_val = _remaining_days(order)
    con_lai = f"{max(con_lai_val, 0)} ngày" if con_lai_val is not None else "Không rõ"
    gia_tri_con_lai_val = _remaining_value(order)
    gia_tri_con_lai = (
        _format_currency(gia_tri_con_lai_val)
        if gia_tri_con_lai_val is not None
        else "0"
    )
    bullet = "\\- "
    text = (
        "*CHI TIẾT ĐƠN HÀNG*\n"
        f"Mã Đơn: `{escape_mdv2(order.ma_don)}`\n\n"
        "*THÔNG TIN SẢN PHẨM*\n"
        f"{bullet}Sản Phẩm: {escape_mdv2(order.san_pham)}\n"
        f"{bullet}Thông Tin: {escape_mdv2(order.thong_tin)}\n"
    )
    if order.slot:
        text += f"{bullet}Slot: {escape_mdv2(order.slot)}\n"
    text += (
        f"{bullet}Ngày Đăng Ký: {escape_mdv2(ngay_dk)}\n"
        f"{bullet}Số Ngày: {escape_mdv2(str(order.so_ngay))}\n"
        f"{bullet}Hết Hạn: {escape_mdv2(het_han)}\n"
        f"{bullet}Còn Lại: {escape_mdv2(con_lai)}\n"
        f"{bullet}Nhà Cung Cấp: {escape_mdv2(order.nguon)}\n"
        f"{bullet}Giá Nhập: {escape_mdv2(_format_currency(order.gia_nhap))}\n"
        f"{bullet}Giá Bán: {escape_mdv2(_format_currency(order.gia_ban))}\n"
        f"{bullet}Giá Trị Còn Lại: {escape_mdv2(gia_tri_con_lai)}\n"
        f"{bullet}Ghi Chú: {escape_mdv2(order.note)}\n\n"
        "*THÔNG TIN KHÁCH HÀNG*\n"
        f"{bullet}Tên Khách Hàng: {escape_mdv2(order.ten_khach)}\n"
    )
    if order.link_khach:
        text += f"{bullet}Liên Hệ: {escape_mdv2(order.link_khach)}"
    return text


async def _edit_or_send_main_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
) -> None:
    message_id = context.user_data.get("main_message_id")
    try:
        if message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        context.user_data["main_message_id"] = sent.message_id
    except TelegramError as exc:
        logger.warning("Cannot edit message (%s). Sending new message.", exc)
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        context.user_data["main_message_id"] = sent.message_id


def _store_prompt_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    context.user_data["prompt_message"] = {"chat_id": chat_id, "message_id": message_id}


async def _delete_prompt_message(context: ContextTypes.DEFAULT_TYPE, bot) -> None:
    prompt = context.user_data.pop("prompt_message", None)
    if not prompt:
        return
    try:
        await bot.delete_message(chat_id=prompt["chat_id"], message_id=prompt["message_id"])
    except TelegramError:
        pass


async def _update_prompt_message(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
) -> bool:
    prompt = context.user_data.get("prompt_message")
    if not prompt:
        return False
    try:
        await context.bot.edit_message_text(
            chat_id=prompt["chat_id"],
            message_id=prompt["message_id"],
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramError as exc:
        logger.warning("Cannot update prompt message: %s. Creating new prompt.", exc)
        sent = await context.bot.send_message(
            chat_id=prompt["chat_id"],
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        _store_prompt_message(context, sent.chat.id, sent.message_id)
        return True
