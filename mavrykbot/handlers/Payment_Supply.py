from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import List, Tuple

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PAYMENT_SUPPLY_TABLE,
    SUPPLY_TABLE,
    OrderListColumns,
    PaymentSupplyColumns,
    SupplyColumns,
)
from mavrykbot.core.utils import escape_mdv2
from mavrykbot.handlers.menu import show_outer_menu

logger = logging.getLogger(__name__)

PAYMENT_PENDING_STATUS = "Chưa Thanh Toán"
PAYMENT_PAID_STATUS = "Đã Thanh Toán"
ORDER_PENDING_STATUS = "Chưa Thanh Toán"
ORDER_PAID_STATUS = "Đã Thanh Toán"
USER_DATA_KEY = "payment_supply_entries"
(
    VIEWING,
) = range(1)

BLANK_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
    b"\x00\x00\x02\x02D\x01\x00;"
)


@dataclass
class SupplyPayment:
    payment_id: int
    source_id: int
    source_name: str
    bank_number: str
    bank_code: str
    expected_amount: int
    round_label: str | None
    order_ids: List[int]
    order_sum: int
    override_amount: int | None = None


def _normalize_amount(value) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _normalize_source(value: str) -> str:
    return re.sub(r"^@", "", (value or "").strip()).lower()


def _format_currency(value: int) -> str:
    return f"{value:,} đ"


def _fetch_orders_for_source(source_name: str) -> Tuple[List[int], int]:
    normalized = _normalize_source(source_name)
    sql = f"""
        SELECT {OrderListColumns.ID}, COALESCE({OrderListColumns.GIA_NHAP}, 0)
        FROM {ORDER_LIST_TABLE}
        WHERE LOWER(REGEXP_REPLACE(TRIM({OrderListColumns.NGUON}), '^@', '')) = %s
          AND ({OrderListColumns.CHECK_FLAG} IS NULL OR {OrderListColumns.CHECK_FLAG} = FALSE)
          AND LOWER(COALESCE({OrderListColumns.TINH_TRANG}, '')) = %s
        ORDER BY {OrderListColumns.ID} ASC
    """
    rows = db.fetch_all(sql, (normalized, ORDER_PENDING_STATUS.lower()))
    order_ids: List[int] = []
    total = 0
    for row_id, gia_nhap in rows:
        order_ids.append(int(row_id))
        total += int(gia_nhap or 0)
    return order_ids, total


def _load_pending_payments() -> List[SupplyPayment]:
    sql = f"""
        SELECT
            ps.{PaymentSupplyColumns.ID},
            ps.{PaymentSupplyColumns.SOURCE_ID},
            ps.{PaymentSupplyColumns.IMPORT},
            ps.{PaymentSupplyColumns.ROUND},
            ps.{PaymentSupplyColumns.STATUS},
            s.{SupplyColumns.SOURCE_NAME},
            s.{SupplyColumns.NUMBER_BANK},
            s.{SupplyColumns.BIN_BANK}
        FROM {PAYMENT_SUPPLY_TABLE} ps
        JOIN {SUPPLY_TABLE} s ON s.{SupplyColumns.ID} = ps.{PaymentSupplyColumns.SOURCE_ID}
        WHERE LOWER(ps.{PaymentSupplyColumns.STATUS}) = LOWER(%s)
        ORDER BY ps.{PaymentSupplyColumns.ID} ASC
    """
    rows = db.fetch_all(sql, (PAYMENT_PENDING_STATUS,))
    payments: List[SupplyPayment] = []
    for row in rows:
        (
            payment_id,
            source_id,
            import_value,
            round_label,
            _status,
            source_name,
            bank_number,
            bank_code,
        ) = row
        expected_amount = _normalize_amount(import_value)
        order_ids, order_sum = _fetch_orders_for_source(source_name)
        payments.append(
            SupplyPayment(
                payment_id=payment_id,
                source_id=source_id,
                source_name=source_name or "",
                bank_number=str(bank_number or "").strip(),
                bank_code=str(bank_code or "").strip(),
                expected_amount=expected_amount,
                round_label=round_label,
                order_ids=order_ids,
                order_sum=order_sum,
            )
        )
    return payments


def build_qr_url(stk: str, bank_code: str, amount: int, note: str) -> str:
    if not stk or not bank_code:
        raise ValueError("Thiếu thông tin ngân hàng.")
    if amount <= 0:
        raise ValueError("Số tiền phải lớn hơn 0.")
    note_encoded = urllib.parse.quote((note or "").strip())
    return f"https://img.vietqr.io/image/{bank_code}-{stk}-compact2.png?amount={amount}&addInfo={note_encoded}"


def fetch_qr_image_bytes(url: str) -> bytes:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    if "image" not in response.headers.get("Content-Type", ""):
        raise ValueError("Dữ liệu trả về không phải ảnh hợp lệ.")
    return response.content


def _build_photo_payload(entry: SupplyPayment, amount: int) -> Tuple[bytes, str]:
    try:
        qr_url = build_qr_url(entry.bank_number, entry.bank_code, amount, entry.source_name)
        qr_bytes = fetch_qr_image_bytes(qr_url)
        return qr_bytes, "qrcode.png"
    except Exception as exc:
        logger.warning("Không thể tạo QR cho %s: %s", entry.source_name, exc)
        return BLANK_GIF, "blank.gif"


def _ensure_entries(context: ContextTypes.DEFAULT_TYPE) -> List[SupplyPayment]:
    entries = context.user_data.get(USER_DATA_KEY)
    if entries is None:
        entries = _load_pending_payments()
        context.user_data[USER_DATA_KEY] = entries
    return entries


async def show_source_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    index: int = 0,
    *,
    force_amount: int | None = None,
):
    query = update.callback_query
    if query:
        await query.answer()

    entries = _ensure_entries(context)
    if not entries:
        message = escape_mdv2("Không có nguồn nào đang cần thanh toán.")
        if query:
            try:
                await query.edit_message_text(message, parse_mode="MarkdownV2")
            except BadRequest:
                await update.effective_chat.send_message(message, parse_mode="MarkdownV2")
        else:
            await update.effective_chat.send_message(message, parse_mode="MarkdownV2")
        context.user_data.pop(USER_DATA_KEY, None)
        await show_outer_menu(update, context)
        return

    index = max(0, min(index, len(entries) - 1))
    context.user_data["payment_supply_index"] = index
    entry = entries[index]
    if force_amount is not None and force_amount > 0:
        entry.override_amount = force_amount
    expected_amount = entry.expected_amount or 0
    actual_amount = entry.order_sum or 0

    override_amount = entry.override_amount if (entry.override_amount is not None and entry.override_amount > 0) else None
    amount_value = override_amount if override_amount is not None else (expected_amount or actual_amount)
    if amount_value <= 0:
        amount_value = expected_amount or actual_amount
    amount_label = "Số tiền yêu cầu (Import)" if override_amount is None else "Số tiền chuyển"
    amount_label_display = escape_mdv2(amount_label)
    amount_str = escape_mdv2(_format_currency(amount_value))
    actual_str = escape_mdv2(_format_currency(actual_amount))

    caption_lines = [
        f"📋 *Thanh Toán Nguồn* `({index + 1}/{len(entries)})`",
        f"*Nguồn:* {escape_mdv2(entry.source_name)}",
        f"*Nội dung chuyển khoản:* `{escape_mdv2(entry.source_name)}`",
    ]
    if entry.round_label:
        caption_lines.append(f"*Vòng:* {escape_mdv2(str(entry.round_label))}")
    caption_lines.extend(
        [
            f"*{amount_label_display}:* {amount_str}",
            f"*Tổng giá nhập chưa thanh toán:* {actual_str}",
            f"*Số tài khoản:* `{escape_mdv2(entry.bank_number or 'Chưa cập nhật')}`",
            f"*Ngân hàng:* {escape_mdv2(entry.bank_code or 'Chưa cập nhật')}",
        ]
    )
    if actual_amount != expected_amount:
        caption_lines.append("")
        caption_lines.append(
            escape_mdv2("Lưu ý: Tổng giá nhập không khớp số tiền cần thanh toán. Kiểm tra trước khi chuyển.")
        )
    if override_amount is not None:
        caption_lines.append(
            escape_mdv2("Đang sử dụng tổng giá nhập chưa thanh toán làm số tiền chuyển.")
        )
    caption_lines.append("")
    caption_lines.append(escape_mdv2("Tên nguồn được dùng làm nội dung thanh toán."))
    caption = "\n".join(caption_lines)

    show_full_button = actual_amount > 0 and actual_amount != expected_amount and override_amount is None

    buttons: list[list[InlineKeyboardButton]] = []
    nav_buttons: list[InlineKeyboardButton] = []
    if index > 0:
        nav_buttons.append(InlineKeyboardButton("Trước", callback_data=f"source_prev|{index}"))
    if index < len(entries) - 1:
        nav_buttons.append(InlineKeyboardButton("Sau", callback_data=f"source_next|{index}"))
    if nav_buttons:
        buttons.append(nav_buttons)
    if show_full_button:
        buttons.append([InlineKeyboardButton("Thanh Toán Toàn Bộ", callback_data=f"source_full|{index}")])
    buttons.append(
        [
            InlineKeyboardButton("Đã Thanh Toán", callback_data=f"source_paid|{index}"),
            InlineKeyboardButton("Kết Thúc", callback_data="exit_to_main"),
        ]
    )
    reply_markup = InlineKeyboardMarkup(buttons)

    photo_bytes, photo_name = _build_photo_payload(entry, amount_value)

    def _make_input_file() -> InputFile:
        bio = BytesIO(photo_bytes)
        bio.seek(0)
        return InputFile(bio, filename=photo_name)

    if query and query.message and query.message.photo:
        try:
            await query.message.edit_media(
                media=InputMediaPhoto(
                    media=_make_input_file(), caption=caption, parse_mode=ParseMode.MARKDOWN_V2
                ),
                reply_markup=reply_markup,
            )
            return
        except BadRequest as exc:
            text = str(exc)
            if "Message is not modified" in text:
                await query.answer("Nội dung không thay đổi.")
                return
            if "parse" in text.lower():
                logger.warning("Markdown parse failed when editing payment QR: %s", exc)
                try:
                    await query.message.edit_media(
                        media=InputMediaPhoto(media=_make_input_file(), caption=caption),
                        reply_markup=reply_markup,
                    )
                    return
                except BadRequest as exc_plain:
                    logger.error("Retry edit_media without Markdown failed: %s", exc_plain)
            logger.debug("edit_media thất bại, gửi mới: %s", exc)

    if query and query.message:
        try:
            await query.message.delete()
        except BadRequest:
            pass

    try:
        await update.effective_chat.send_photo(
            photo=_make_input_file(),
            caption=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup,
        )
    except BadRequest as exc:
        text_err = str(exc).lower()
        if "parse" in text_err:
            logger.warning("Markdown parse failed when sending payment QR: %s", exc)
            await update.effective_chat.send_photo(
                photo=_make_input_file(),
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            raise

async def start_payment_supply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    context.user_data.pop(USER_DATA_KEY, None)
    if query:
        await query.answer("Đang tải dữ liệu...", show_alert=False)
    await show_source_payment(update, context, index=0)
    return VIEWING


def _update_payment_supply(payment_id: int, paid_value: int, current_round: str | None) -> None:
    today_str = datetime.now().strftime("%d/%m/%Y")
    if current_round and str(current_round).strip():
        new_round = f"{current_round} - {today_str}"
    else:
        new_round = today_str
    sql = f"""
        UPDATE {PAYMENT_SUPPLY_TABLE}
        SET {PaymentSupplyColumns.STATUS} = %s,
            {PaymentSupplyColumns.PAID} = %s,
            {PaymentSupplyColumns.ROUND} = %s
        WHERE {PaymentSupplyColumns.ID} = %s
    """
    db.execute(sql, (PAYMENT_PAID_STATUS, paid_value, new_round, payment_id))


def _mark_orders_paid(order_ids: List[int]) -> None:
    if not order_ids:
        return
    placeholders = ",".join(["%s"] * len(order_ids))
    sql = f"""
        UPDATE {ORDER_LIST_TABLE}
        SET {OrderListColumns.CHECK_FLAG} = TRUE,
            {OrderListColumns.TINH_TRANG} = %s
        WHERE {OrderListColumns.ID} IN ({placeholders})
    """
    params = [ORDER_PAID_STATUS, *order_ids]
    db.execute(sql, params)


async def handle_source_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Đang xử lý...", show_alert=False)
    entries: List[SupplyPayment] = context.user_data.get(USER_DATA_KEY, [])
    if not entries:
        await query.answer("Không có dữ liệu nguồn.", show_alert=True)
        return VIEWING

    index = int(query.data.split("|")[1])
    if index >= len(entries):
        await query.answer("Nguồn không tồn tại nữa.", show_alert=True)
        return VIEWING
    entry = entries[index]

    try:
        order_ids, order_sum = _fetch_orders_for_source(entry.source_name)
    except Exception as exc:
        logger.error("Lỗi khi truy vấn đơn hàng của %s: %s", entry.source_name, exc, exc_info=True)
        await query.answer("Không thể lấy đơn hàng cần cập nhật.", show_alert=True)
        return VIEWING

    if not order_ids:
        await query.answer("Không tìm thấy đơn nào cần cập nhật.", show_alert=True)
        return VIEWING

    override_amount = entry.override_amount if (entry.override_amount is not None and entry.override_amount > 0) else None
    paid_value = override_amount or order_sum or entry.expected_amount
    try:
        _update_payment_supply(entry.payment_id, paid_value, entry.round_label)
        _mark_orders_paid(order_ids)
    except Exception as exc:
        logger.error("Lỗi khi cập nhật trạng thái thanh toán %s: %s", entry.source_name, exc, exc_info=True)
        await query.answer("Không thể cập nhật cơ sở dữ liệu.", show_alert=True)
        return VIEWING

    await query.answer("Đã xác nhận thanh toán!", show_alert=True)
    entries.pop(index)
    if entries:
        context.user_data[USER_DATA_KEY] = entries
        await show_source_payment(update, context, index=min(index, len(entries) - 1))
    else:
        context.user_data.pop(USER_DATA_KEY, None)
        await show_source_payment(update, context, index=0)
    return VIEWING


async def handle_source_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, index_str = query.data.split("|")
    index = int(index_str)
    if action == "source_next":
        new_index = index + 1
    else:
        new_index = index - 1
    await show_source_payment(update, context, index=new_index)
    return VIEWING


async def handle_full_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    entries: List[SupplyPayment] = context.user_data.get(USER_DATA_KEY, [])
    if not entries:
        await query.answer("Không có dữ liệu nguồn.", show_alert=True)
        return VIEWING
    index = int(query.data.split("|")[1])
    if index >= len(entries):
        await query.answer("Nguồn không tồn tại nữa.", show_alert=True)
        return VIEWING
    entry = entries[index]
    try:
        _, latest_sum = _fetch_orders_for_source(entry.source_name)
    except Exception as exc:
        logger.error("Không thể lấy tổng giá nhập cho %s: %s", entry.source_name, exc, exc_info=True)
        await query.answer("Không thể lấy số tiền tổng hiện tại.", show_alert=True)
        return VIEWING
    amount = latest_sum or entry.order_sum
    if not amount or amount <= 0:
        await query.answer("Chưa có tổng giá nhập để thanh toán.", show_alert=True)
        return VIEWING
    entry.order_sum = amount
    entry.override_amount = amount
    await show_source_payment(
        update, context, index=index, force_amount=amount
    )
    return VIEWING


async def handle_exit_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    for key in list(context.user_data.keys()):
        if key.startswith("payment_"):
            context.user_data.pop(key, None)
    context.user_data.pop(USER_DATA_KEY, None)
    await show_outer_menu(update, context)
    return ConversationHandler.END


def get_payment_supply_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_payment_supply, pattern="^payment_source$"),
            CommandHandler("payment_source", start_payment_supply),
        ],
        states={
            VIEWING: [
                CallbackQueryHandler(handle_source_navigation, pattern="^source_(next|prev)\\|"),
                CallbackQueryHandler(handle_full_payment, pattern="^source_full\\|"),
                CallbackQueryHandler(handle_source_paid, pattern="^source_paid\\|"),
                CallbackQueryHandler(handle_exit_to_main, pattern="^exit_to_main$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handle_exit_to_main),
            CallbackQueryHandler(handle_exit_to_main, pattern="^exit_to_main$"),
        ],
        name="payment_supply_conversation",
        persistent=False,
        allow_reentry=True,
    )
