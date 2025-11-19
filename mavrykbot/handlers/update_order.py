import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PRODUCT_PRICE_TABLE,
    SUPPLY_PRICE_TABLE,
    SUPPLY_TABLE,
    OrderListColumns,
    ProductPriceColumns,
    SupplyColumns,
    SupplyPriceColumns,
)
from mavrykbot.core.utils import chuan_hoa_gia, escape_mdv2, normalize_product_duration
from mavrykbot.handlers.add_order import tinh_ngay_het_han
from mavrykbot.handlers.menu import show_main_selector

logger = logging.getLogger(__name__)

DATE_FMT = "%d/%m/%Y"

(
    SELECT_MODE,
    INPUT_VALUE,
    SELECT_ACTION,
    EDIT_CHOOSE_FIELD,
    EDIT_INPUT_SIMPLE,
    EDIT_INPUT_NGUON,
    EDIT_INPUT_SO_NGAY,
    EDIT_INPUT_TEN_KHACH,
    EDIT_INPUT_LINK_KHACH,
) = range(9)


@dataclass
class OrderRecord:
    db_id: int
    ma_don: str
    san_pham: str
    thong_tin: str
    slot: str
    ngay_dang_ky: Optional[date]
    so_ngay: int
    het_han: Optional[date]
    nguon: str
    gia_nhap: int
    gia_ban: int
    note: str
    ten_khach: str
    link_khach: str


ORDER_SELECT_FIELDS: Sequence[str] = (
    OrderListColumns.ID,
    OrderListColumns.ID_DON_HANG,
    OrderListColumns.SAN_PHAM,
    OrderListColumns.THONG_TIN_SAN_PHAM,
    OrderListColumns.KHACH_HANG,
    OrderListColumns.LINK_LIEN_HE,
    OrderListColumns.SLOT,
    OrderListColumns.NGAY_DANG_KI,
    OrderListColumns.SO_NGAY_DA_DANG_KI,
    OrderListColumns.HET_HAN,
    OrderListColumns.NGUON,
    OrderListColumns.GIA_NHAP,
    OrderListColumns.GIA_BAN,
    OrderListColumns.NOTE,
)

FIELD_CONFIG: Dict[str, Dict[str, object]] = {
    "THONG_TIN": {
        "label": "Thông tin",
        "column": OrderListColumns.THONG_TIN_SAN_PHAM,
        "attr": "thong_tin",
        "state": EDIT_INPUT_SIMPLE,
    },
    "TEN_KHACH": {
        "label": "Tên khách",
        "column": OrderListColumns.KHACH_HANG,
        "attr": "ten_khach",
        "state": EDIT_INPUT_TEN_KHACH,
    },
    "LINK_KHACH": {
        "label": "Link khách",
        "column": OrderListColumns.LINK_LIEN_HE,
        "attr": "link_khach",
        "state": EDIT_INPUT_LINK_KHACH,
    },
    "SLOT": {
        "label": "Slot",
        "column": OrderListColumns.SLOT,
        "attr": "slot",
        "state": EDIT_INPUT_SIMPLE,
    },
    "NGUON": {
        "label": "Nguồn",
        "column": OrderListColumns.NGUON,
        "attr": "nguon",
        "state": EDIT_INPUT_NGUON,
    },
    "SO_NGAY": {
        "label": "Số ngày",
        "column": OrderListColumns.SO_NGAY_DA_DANG_KI,
        "attr": "so_ngay",
        "state": EDIT_INPUT_SO_NGAY,
    },
    "GIA_NHAP": {
        "label": "Giá nhập",
        "column": OrderListColumns.GIA_NHAP,
        "attr": "gia_nhap",
        "state": EDIT_INPUT_SIMPLE,
    },
    "GIA_BAN": {
        "label": "Giá bán",
        "column": OrderListColumns.GIA_BAN,
        "attr": "gia_ban",
        "state": EDIT_INPUT_SIMPLE,
    },
    "NOTE": {
        "label": "Ghi chú",
        "column": OrderListColumns.NOTE,
        "attr": "note",
        "state": EDIT_INPUT_SIMPLE,
    },
}

FIELD_MENU_LAYOUT: List[List[Optional[str]]] = [
    ["THONG_TIN", "TEN_KHACH", "LINK_KHACH"],
    ["SLOT", "NGUON", "SO_NGAY"],
    ["GIA_NHAP", "GIA_BAN", "NOTE"],
]


def _today() -> date:
    return datetime.now().date()


def _format_date(value: Optional[date]) -> str:
    return value.strftime(DATE_FMT) if value else ""


def _format_currency(value: Optional[int]) -> str:
    amount = int(value or 0)
    return "{:,}".format(amount).replace(",", ".")


def _parse_date(value) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", DATE_FMT):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


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


def _round_up_to_thousand(value: int) -> int:
    if value <= 0:
        return 0
    return ((int(value) + 999) // 1000) * 1000


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




def _query_orders_by_id(search_term: str) -> List[OrderRecord]:
    sql = f"""
        SELECT {", ".join(ORDER_SELECT_FIELDS)}
        FROM {ORDER_LIST_TABLE}
        WHERE LOWER({OrderListColumns.ID_DON_HANG}) = LOWER(%s)
        ORDER BY {OrderListColumns.ID} DESC
    """
    rows = db.fetch_all(sql, (search_term.strip(),))
    return [_build_order(row) for row in rows]


def _query_orders_by_info(search_term: str) -> List[OrderRecord]:
    sql = f"""
        SELECT {", ".join(ORDER_SELECT_FIELDS)}
        FROM {ORDER_LIST_TABLE}
        WHERE {OrderListColumns.THONG_TIN_SAN_PHAM} ILIKE %s
           OR {OrderListColumns.SAN_PHAM} ILIKE %s
        ORDER BY {OrderListColumns.ID} DESC
    """
    like_term = f"%{search_term.strip()}%"
    rows = db.fetch_all(sql, (like_term, like_term))
    return [_build_order(row) for row in rows]

async def start_update_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Mã Đơn", callback_data="mode_id"),
            InlineKeyboardButton("Thông Tin Sản Phẩm", callback_data="mode_info"),
        ],
        [InlineKeyboardButton("Hủy", callback_data="cancel_update")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_text = "Vui lòng chọn chế độ tìm kiếm:"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, reply_markup=reply_markup
        )
        context.user_data["main_message_id"] = update.callback_query.message.message_id
    else:
        msg = await update.message.reply_text(message_text, reply_markup=reply_markup)
        context.user_data["main_message_id"] = msg.message_id
    return SELECT_MODE


async def select_check_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["check_mode"] = query.data
    prompt = (
        "Vui lòng nhập *Mã Đơn Hàng*:"
        if query.data == "mode_id"
        else "Vui Lòng Nhập *Thông Tin Sản Phẩm* Cần Tìm:"
    )
    await query.edit_message_text(
        prompt,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Hủy", callback_data="cancel_update")]]
        ),
    )
    return INPUT_VALUE


async def input_value_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    search_term = (update.message.text or "").strip()
    await update.message.delete()

    main_message_id = context.user_data.get("main_message_id")
    chat_id = update.effective_chat.id
    check_mode = context.user_data.get("check_mode")

    await _edit_or_send_main_message(
        context,
        chat_id,
        "Đang tìm kiếm...",
        reply_markup=None,
    )

    try:
        if check_mode == "mode_id":
            matched = _query_orders_by_id(search_term)
        else:
            matched = _query_orders_by_info(search_term)
    except Exception as exc:
        logger.error("SQL search failed: %s", exc, exc_info=True)
        await _edit_or_send_main_message(
            context,
            chat_id,
            "Không thể tìm đơn hàng (lỗi DB).",
        )
        return await end_update(update, context)

    if not matched:
        await _edit_or_send_main_message(
            context,
            chat_id,
            "Không tìm thấy đơn hàng phù hợp.",
        )
        return await end_update(update, context)

    context.user_data["matched_orders"] = matched
    context.user_data["current_match_index"] = 0
    return await show_matched_order(update, context)


async def show_matched_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    direction: str = "stay",
    success_notice: Optional[str] = None,
) -> int:
    query = update.callback_query
    if query and not getattr(query, "answered", False):
        await query.answer()

    matched_orders: List[OrderRecord] = context.user_data.get("matched_orders", [])
    if not matched_orders:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Không có đơn hàng nào."
        )
        return await end_update(update, context)

    index = context.user_data.get("current_match_index", 0)
    if direction == "next":
        index += 1
    elif direction == "prev":
        index -= 1
    index = min(max(index, 0), len(matched_orders) - 1)
    context.user_data["current_match_index"] = index

    order = matched_orders[index]
    message_text = _format_order_message(order)
    if success_notice:
        message_text = f"_{escape_mdv2(success_notice)}_\n\n{message_text}"

    buttons: List[List[InlineKeyboardButton]] = []
    nav_row: List[InlineKeyboardButton] = []
    if len(matched_orders) > 1:
        if index > 0:
            nav_row.append(InlineKeyboardButton("Quay lại", callback_data="nav_prev"))
        if index < len(matched_orders) - 1:
            nav_row.append(InlineKeyboardButton("Tiếp", callback_data="nav_next"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton("Gia hạn", callback_data=f"action_extend|{order.ma_don}"),
            InlineKeyboardButton("Xóa", callback_data=f"action_delete|{order.ma_don}"),
            InlineKeyboardButton("Sửa", callback_data=f"action_edit|{order.ma_don}"),
        ]
    )
    buttons.append(
        [InlineKeyboardButton("Hủy & về menu", callback_data="cancel_update")]
    )

    if len(matched_orders) > 1:
        message_text += f"\n\nKết quả ({index + 1}/{len(matched_orders)})"

    await _edit_or_send_main_message(
        context,
        update.effective_chat.id,
        message_text,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SELECT_ACTION


def _find_order_by_ma(
    orders: List[OrderRecord], ma_don: str
) -> Optional[OrderRecord]:
    ma_lower = ma_don.strip().lower()
    for record in orders:
        if record.ma_don.lower() == ma_lower:
            return record
    return None


def _lookup_product_profile(
    product_name: str,
) -> Optional[Sequence]:
    sql = f"""
        SELECT {ProductPriceColumns.ID},
               {ProductPriceColumns.PCT_CTV},
               {ProductPriceColumns.PCT_KHACH}
        FROM {PRODUCT_PRICE_TABLE}
        WHERE LOWER({ProductPriceColumns.SAN_PHAM}) = LOWER(%s)
        LIMIT 1
    """
    return db.fetch_one(sql, (product_name.strip(),))


def _lookup_source_price(product_id: int, source_name: str) -> Optional[int]:
    sql = f"""
        SELECT sp.{SupplyPriceColumns.PRICE}
        FROM {SUPPLY_PRICE_TABLE} sp
        JOIN {SUPPLY_TABLE} s
          ON sp.{SupplyPriceColumns.SOURCE_ID} = s.{SupplyColumns.ID}
        WHERE sp.{SupplyPriceColumns.PRODUCT_ID} = %s
          AND LOWER(s.{SupplyColumns.SOURCE_NAME}) = LOWER(%s)
        LIMIT 1
    """
    row = db.fetch_one(sql, (product_id, source_name.strip()))
    return int(row[0]) if row and row[0] is not None else None


def _lookup_highest_price(product_id: int) -> int:
    sql = f"""
        SELECT MAX({SupplyPriceColumns.PRICE})
        FROM {SUPPLY_PRICE_TABLE}
        WHERE {SupplyPriceColumns.PRODUCT_ID} = %s
    """
    row = db.fetch_one(sql, (product_id,))
    return int(row[0]) if row and row[0] else 0

async def extend_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    product_profile = _lookup_product_profile(order.san_pham)
    gia_nhap_moi = order.gia_nhap
    gia_ban_moi = order.gia_ban

    if product_profile:
        product_id, pct_ctv, pct_khach = product_profile
        pct_ctv = Decimal(str(pct_ctv or 1))
        pct_khach = Decimal(str(pct_khach or 1))

        nguon_price = _lookup_source_price(product_id, order.nguon)
        if nguon_price is not None and nguon_price > 0:
            gia_nhap_moi = nguon_price

        highest_price = _lookup_highest_price(product_id)
        if highest_price > 0:
            high_price = Decimal(highest_price)
            ma_upper = order.ma_don.upper()
            if ma_upper.startswith("MAVC"):
                gia_ban_moi = int(high_price * pct_ctv)
            elif ma_upper.startswith("MAVL"):
                gia_ban_moi = int((high_price * pct_ctv) * pct_khach)
            elif ma_upper.startswith("MAVK"):
                gia_ban_moi = gia_nhap_moi

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

async def start_edit_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ma_don = query.data.split("|", 1)[1].strip()
    context.user_data["edit_ma_don"] = ma_don
    keyboard: List[List[InlineKeyboardButton]] = []
    for row in FIELD_MENU_LAYOUT:
        buttons: List[InlineKeyboardButton] = []
        for field_key in row:
            if not field_key:
                continue
            cfg = FIELD_CONFIG[field_key]
            buttons.append(
                InlineKeyboardButton(
                    str(cfg["label"]),
                    callback_data=f"edit|{field_key}"
                )
            )
        if buttons:
            keyboard.append(buttons)
    keyboard.append([InlineKeyboardButton("Quay Lại", callback_data="back_to_order")])
    await query.edit_message_text(
        "Chọn trường muốn chỉnh sửa:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_CHOOSE_FIELD


async def choose_field_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("|", 1)
    if len(parts) < 2 or parts[1] not in FIELD_CONFIG:
        await query.edit_message_text("Trường không hợp lệ.")
        return await end_update(update, context)

    field_key = parts[1]
    context.user_data["edit_field"] = field_key
    cfg = FIELD_CONFIG[field_key]

    keyboard = [[InlineKeyboardButton("Hủy", callback_data="cancel_update")]]
    if field_key == "LINK_KHACH":
        keyboard.insert(0, [InlineKeyboardButton("Bỏ trống", callback_data="skip_link_khach")])
    # --- BẮT ĐẦU PHẦN THAY ĐỔI ---
    # Lưu tin nhắn prompt hiện tại để có thể chỉnh sửa sau (dành cho EDIT_INPUT_TEN_KHACH)
    _store_prompt_message(context, query.message.chat.id, query.message.message_id)
    # --- KẾT THÚC PHẦN THAY ĐỔI ---
    
    await query.edit_message_text(
        f"Nhập giá trị mới cho *{cfg['label']}*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return cfg["state"]


async def back_to_order_display(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    return await show_matched_order(update, context)


def _persist_field_change(order: OrderRecord, field_key: str, value):
    cfg = FIELD_CONFIG[field_key]
    column = cfg["column"]
    db.execute(
        f"UPDATE {ORDER_LIST_TABLE} SET {column} = %s WHERE {OrderListColumns.ID} = %s",
        (value, order.db_id),
    )
    setattr(order, cfg["attr"], value)


async def _finalize_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    field_key: Optional[str] = None,
    value,
    success_notice: Optional[str] = None,
) -> int:
    if field_key is None:
        field_key = context.user_data.get("edit_field")
    if not field_key:
        await update.message.reply_text("Không xác định trường cần cập nhật.")
        return EDIT_INPUT_SIMPLE
    try:
        order = _get_active_order(context)
        _persist_field_change(order, field_key, value)
    except Exception as exc:
        logger.error("Cập nhật trường %s thất bại: %s", field_key, exc, exc_info=True)
        await update.message.reply_text("Không thể cập nhật DB.")
        return FIELD_CONFIG[field_key]["state"]
    if update.message:
        await update.message.delete()
    notice = success_notice or f"Đã cập nhật {FIELD_CONFIG[field_key]['label']}."
    return await show_matched_order(update, context, success_notice=notice)

async def input_new_simple_value_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    field_key = context.user_data.get("edit_field")
    text = (update.message.text or "").strip()
    if not field_key:
        await update.message.reply_text("Không xác định trường cần cập nhật.")
        return EDIT_INPUT_SIMPLE
    if field_key in {"GIA_NHAP", "GIA_BAN"}:
        _, number = chuan_hoa_gia(text)
        value = number
    else:
        if not text:
            await update.message.reply_text("Giá trị không được để trống.")
            return FIELD_CONFIG[field_key]["state"]
        value = text
    return await _finalize_edit(update, context, field_key=field_key, value=value)


async def input_new_nguon_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Nhập tên nguồn hợp lệ.")
        return EDIT_INPUT_NGUON
    sql = f"""
        SELECT 1 FROM {SUPPLY_TABLE}
        WHERE LOWER({SupplyColumns.SOURCE_NAME}) = LOWER(%s)
        LIMIT 1
    """
    try:
        exists = db.fetch_one(sql, (text,))
    except Exception as exc:
        logger.error("Tìm nguồn lỗi: %s", exc, exc_info=True)
        await update.message.reply_text("Không thể kiểm tra nguồn.")
        return EDIT_INPUT_NGUON
    if not exists:
        await update.message.reply_text("Nguồn không tồn tại.")
        return EDIT_INPUT_NGUON
    return await _finalize_edit(update, context, field_key="NGUON", value=text)


async def input_new_so_ngay_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    try:
        value = int(text)
    except ValueError:
        await update.message.reply_text("Vui lòng nhập số nguyên.")
        return EDIT_INPUT_SO_NGAY
    if value <= 0:
        await update.message.reply_text("Số ngày phải > 0.")
        return EDIT_INPUT_SO_NGAY
    return await _finalize_edit(update, context, field_key="SO_NGAY", value=value)


async def input_new_ten_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Ten khach khong duoc rong.")
        return EDIT_INPUT_TEN_KHACH

    try:
        order = _get_active_order(context)
        _persist_field_change(order, "TEN_KHACH", text)
    except Exception as exc:
        logger.error("Cap nhat ten khach that bai: %s", exc, exc_info=True)
        await update.message.reply_text("Khong the cap nhat ten khach.")
        return EDIT_INPUT_TEN_KHACH

    if update.message:
        await update.message.delete()

    context.user_data["after_name_link"] = True
    context.user_data["edit_field"] = "LINK_KHACH"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Bỏ qua", callback_data="skip_link_after_name")],
        [InlineKeyboardButton("Hủy", callback_data="cancel_update")],
    ])
    prompt_text = "Nhập thông tin liên hệ khách hàng (hoặc Bỏ qua):"
    await _update_prompt_message(context, prompt_text, reply_markup=keyboard)
    return EDIT_INPUT_LINK_KHACH


async def input_new_link_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    text = (update.message.text or "").strip()
    after_name = context.user_data.pop("after_name_link", False)
    success = "Da cap nhat ten khach & lien he." if after_name else None
    context.user_data["edit_field"] = "LINK_KHACH"
    return await _finalize_edit(
        update, context, field_key="LINK_KHACH", value=text, success_notice=success
    )


async def skip_link_after_name_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer("Bỏ Qua Liên Hệ.")
    context.user_data.pop("after_name_link", None)
    context.user_data["edit_field"] = "LINK_KHACH"
    return await _finalize_edit(
        update, context, field_key="LINK_KHACH", value="", success_notice="Đã Cập Nhật Liên Hệ"
    )


async def skip_link_khach_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()
    return await _finalize_edit(
        update, context, field_key="LINK_KHACH", value="", success_notice="Đã Bỏ Qua Liên Hệ."
    )


async def skip_link_after_name_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer("Bo qua lien he.")
    context.user_data.pop("after_name_link", None)
    context.user_data.pop("edit_field", None)
    return await show_matched_order(update, context, success_notice="Đã Cập Nhật Tên Khách")

async def end_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await asyncio.sleep(1)
    await _delete_prompt_message(context, context.bot)
    main_message_id = context.user_data.get("main_message_id")
    try:
        if update.callback_query:
            await show_main_selector(update, context, edit=True)
        else:
            if main_message_id:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id, message_id=main_message_id
                )
            await show_main_selector(update, context, edit=False)
    except Exception as exc:
        logger.warning("Không thể quay lại menu: %s", exc)
        await show_main_selector(update, context, edit=False)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer("Đã Hủy")
    return await end_update(update, context)


def get_update_order_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("update", start_update_order),
            CallbackQueryHandler(start_update_order, pattern="^update$"),
        ],
        states={
            SELECT_MODE: [
                CallbackQueryHandler(select_check_mode, pattern="^mode_.*$"),
            ],
            INPUT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_value_handler)
            ],
            SELECT_ACTION: [
                CallbackQueryHandler(cancel_update, pattern="^cancel_update$"),
                CallbackQueryHandler(
                    lambda u, c: show_matched_order(u, c, "prev"),
                    pattern="^nav_prev$",
                ),
                CallbackQueryHandler(
                    lambda u, c: show_matched_order(u, c, "next"),
                    pattern="^nav_next$",
                ),
                CallbackQueryHandler(extend_order, pattern=r"^action_extend\|"),
                CallbackQueryHandler(delete_order, pattern=r"^action_delete\|"),
                CallbackQueryHandler(start_edit_update, pattern=r"^action_edit\|"),
            ],
            EDIT_CHOOSE_FIELD: [
                CallbackQueryHandler(choose_field_to_edit, pattern=r"^edit\|"),
                CallbackQueryHandler(back_to_order_display, pattern="^back_to_order$"),
            ],
            EDIT_INPUT_SIMPLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_simple_value_handler
                )
            ],
            EDIT_INPUT_NGUON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_new_nguon_handler)
            ],
            EDIT_INPUT_SO_NGAY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_so_ngay_handler
                )
            ],
            EDIT_INPUT_TEN_KHACH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_ten_khach_handler
                )
            ],
            EDIT_INPUT_LINK_KHACH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_link_khach_handler
                ),
                CallbackQueryHandler(skip_link_khach_handler, pattern="^skip_link_khach$"),
                CallbackQueryHandler(skip_link_after_name_handler, pattern="^skip_link_after_name$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_update, pattern="^cancel_update$"),
            CommandHandler("cancel", cancel_update),
        ],
        name="update_order_conversation",
        persistent=False,
        allow_reentry=True,
    )
