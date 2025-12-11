from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

import requests
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import ContextTypes

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
from mavrykbot.core.config import load_topic_config
from mavrykbot.core.utils import escape_mdv2

TOPIC_CONFIG = load_topic_config()

SEND_DUE_ORDER_TO_TOPIC = TOPIC_CONFIG.send_due_order_to_topic
SEND_ERROR_TO_TOPIC = TOPIC_CONFIG.send_error_to_topic
DUE_ORDER_GROUP_ID = TOPIC_CONFIG.due_order_group_id
DUE_ORDER_TOPIC_ID = TOPIC_CONFIG.due_order_topic_id
ERROR_GROUP_ID = TOPIC_CONFIG.error_group_id
ERROR_TOPIC_ID = TOPIC_CONFIG.error_topic_id

logger = logging.getLogger(__name__)

TARGET_STATUS = "Cần Gia Hạn"
TARGET_DAYS_LEFT = 4
MAX_DUE_ORDERS = 20
QR_TEMPLATE = (
    "https://img.vietqr.io/image/VPB-mavpre-compact2.png?amount={amount}"
    "&addInfo={order_id}&accountName=NGO%20LE%20NGOC%20HUNG"
)


@dataclass
class DueOrder:
    db_id: int
    order_code: str
    product_name: str
    description: str
    customer_name: str
    customer_link: str
    slot: str
    start_date: Optional[date]
    duration_days: Optional[int]
    expiry_date: Optional[date]
    source: str
    note: str
    sale_price: int
    days_left: int


def _coerce_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


def _round_thousand(value: int | Decimal) -> int:
    """Round positive numbers up to the nearest thousand; otherwise return 0."""
    try:
        number = int(Decimal(value))
    except Exception:
        return 0
    if number <= 0:
        return 0
    return ((number + 999) // 1000) * 1000


def _calc_sale_price(
    order_code: str,
    base_price: int | Decimal | None,
    pct_ctv: Decimal | None,
    pct_khach: Decimal | None,
) -> int:
    """
    Compute sale price using the max supply price and percentage rules.
    - MAVC: price * pct_ctv
    - MAVL: price * pct_ctv * pct_khach
    - other: base price (no multiplier)
    """
    try:
        price_value = Decimal(str(base_price)) if base_price is not None else Decimal(0)
    except Exception:
        price_value = Decimal(0)

    pct_ctv_val = Decimal(str(pct_ctv)) if pct_ctv is not None else Decimal("1.0")
    pct_khach_val = Decimal(str(pct_khach)) if pct_khach is not None else Decimal("1.0")

    ma = (order_code or "").upper()
    if ma.startswith("MAVC"):
        gia_ban = price_value * pct_ctv_val
    elif ma.startswith("MAVL"):
        gia_ban = price_value * pct_ctv_val * pct_khach_val
    else:
        gia_ban = price_value
    return _round_thousand(gia_ban)


def fetch_due_orders(limit: int = MAX_DUE_ORDERS) -> list[DueOrder]:
    """
    Query PostgreSQL to find orders that need extension.
    Requirement: order_list.status indicates "Cần Gia Hạn"
    and remaining days equal TARGET_DAYS_LEFT.
    """

    sql = f"""
        SELECT
            ol.{OrderListColumns.ID},
            ol.{OrderListColumns.ID_DON_HANG},
            ol.{OrderListColumns.SAN_PHAM},
            ol.{OrderListColumns.THONG_TIN_SAN_PHAM},
            ol.{OrderListColumns.KHACH_HANG},
            ol.{OrderListColumns.LINK_LIEN_HE},
            ol.{OrderListColumns.SLOT},
            ol.{OrderListColumns.NGAY_DANG_KI},
            ol.{OrderListColumns.SO_NGAY_DA_DANG_KI},
            ol.{OrderListColumns.HET_HAN},
            ol.{OrderListColumns.NGUON},
            ol.{OrderListColumns.NOTE},
            ol.{OrderListColumns.GIA_BAN},
            pp.{ProductPriceColumns.ID} AS product_id,
            pp.{ProductPriceColumns.PCT_CTV},
            pp.{ProductPriceColumns.PCT_KHACH},
            sp_max.max_price AS max_supply_price
        FROM {ORDER_LIST_TABLE} AS ol
        LEFT JOIN {PRODUCT_PRICE_TABLE} AS pp
            ON TRIM(pp.{ProductPriceColumns.SAN_PHAM}) = TRIM(ol.{OrderListColumns.SAN_PHAM})
        LEFT JOIN (
            SELECT
                sp.{SupplyPriceColumns.PRODUCT_ID} AS product_id,
                MAX(sp.{SupplyPriceColumns.PRICE}) AS max_price
            FROM {SUPPLY_PRICE_TABLE} AS sp
            GROUP BY sp.{SupplyPriceColumns.PRODUCT_ID}
        ) AS sp_max
            ON sp_max.product_id = pp.{ProductPriceColumns.ID}
        WHERE LOWER(ol.{OrderListColumns.TINH_TRANG}) = LOWER(%s)
        ORDER BY ol.{OrderListColumns.HET_HAN} ASC
        LIMIT %s
    """
    rows = db.fetch_all(sql, (TARGET_STATUS, limit))
    due_orders: list[DueOrder] = []
    today = date.today()
    for row in rows:
        (
            db_id,
            order_code,
            product,
            description,
            customer,
            customer_link,
            slot,
            start_date,
            duration_days,
            expiry_date,
            source,
            note,
            ol_price,
            product_id,
            pct_ctv,
            pct_khach,
            supply_max_price,
        ) = row
        expiry = _coerce_date(expiry_date)
        days_left = (expiry - today).days if expiry else 0
        if days_left != TARGET_DAYS_LEFT:
            continue

        # Luôn dùng giá cao nhất của supply_price (theo sản phẩm) để tính, nhân theo tỷ lệ.
        base_sale_price = supply_max_price if supply_max_price is not None else ol_price

        sale_price = _calc_sale_price(order_code, base_sale_price, pct_ctv, pct_khach)
        if sale_price <= 0 and ol_price:
            sale_price = _round_thousand(ol_price)

        due_orders.append(
            DueOrder(
                db_id=int(db_id),
                order_code=str(order_code or "").strip(),
                product_name=str(product or "").strip(),
                description=str(description or "").strip(),
                customer_name=str(customer or "").strip(),
                customer_link=str(customer_link or "").strip(),
                slot=str(slot or "").strip(),
                start_date=_coerce_date(start_date),
                duration_days=int(duration_days) if duration_days else None,
                expiry_date=_coerce_date(expiry_date),
                source=str(source or "").strip(),
                note=str(note or "").strip(),
                sale_price=int(sale_price),
                days_left=int(days_left),
            )
        )
    return due_orders


def _format_currency(value: int) -> str:
    if value <= 0:
        return "Chưa Xác Định"
    return f"{value:,} VND"

def _clean(text: str | None) -> str:
    """Return plain text for captions (avoid Markdown parsing issues)."""
    return str(text or "").strip()


def _build_caption(order: DueOrder, index: int, total: int) -> tuple[str, Optional[BytesIO]]:
    header = (
        f"Đơn Cần Gia Hạn ({index + 1}/{total})\n"
        f"Mã Đơn: { _clean(order.order_code)}\n"
        f"Sản Phẩm: {_clean(order.product_name)}\n"
        f"Còn Lại: {order.days_left} ngay"
    )
    info_lines = []
    if order.description:
        info_lines.append(f"- Mô tả: {_clean(order.description)}")
    if order.slot:
        info_lines.append(f"- Slot: {_clean(order.slot)}")
    if order.start_date:
        info_lines.append(f"- Ngày Đăng ký: {_clean(order.start_date.strftime('%d/%m/%Y'))}")
    if order.duration_days:
        info_lines.append(f"- Thời Hạn: {order.duration_days} ngay")
    if order.expiry_date:
        info_lines.append(f"- Ngày Hết Hạn: {_clean(order.expiry_date.strftime('%d/%m/%Y'))}")

    customer_lines = [
        f"- Tên Khách: {_clean(order.customer_name or '---')}",
    ]
    if order.customer_link:
        customer_lines.append(f"- Liên Hệ: {_clean(order.customer_link)}")

    price_text = _format_currency(order.sale_price)

    body = "\n".join(info_lines)
    customer_block = "\n".join(customer_lines)

    caption = (
        f"{header}\n\n"
        f"THÔNG TIN SẢN PHẨM\n"
        f"{body}\n"
        f"- Giá Bán: {price_text}\n\n"
        f"THÔNG TIN KHÁCH HÀNG\n"
        f"{customer_block}\n\n"
        f"vui lòng chuyển khoản đúng số tiền và mã đơn hàng.\n"
        f"Xin cám ơn!"
    )

    qr_image = None
    if order.sale_price > 0:
        try:
            qr_url = QR_TEMPLATE.format(amount=order.sale_price, order_id=order.order_code)
            response = requests.get(qr_url, timeout=10)
            response.raise_for_status()
            qr_image = BytesIO(response.content)
        except requests.RequestException as exc:
            logger.warning("Failed generating QR for %s: %s", order.order_code, exc)

    return caption, qr_image


def _build_caption_pretty(order: DueOrder, index: int, total: int) -> tuple[str, Optional[BytesIO]]:
    """
    Build a cleaner, plain-text caption for due-order notifications.
    ASCII separators only (parse_mode=None) to avoid Markdown issues.
    """
    lines: list[str] = []
    lines.append(f"📦 Đơn hàng đến hạn ({index + 1}/{total})")
    lines.append(f"🧰 Sản phẩm: {_clean(order.product_name)}")
    lines.append(f"🆔 Mã đơn: {_clean(order.order_code)}")
    lines.append(f"⏳ Còn lại: {order.days_left} ngày")

    lines.append("──────🧾 THÔNG TIN SẢN PHẨM ──────")
    if order.description:
        lines.append(f"📝 Mô tả: {_clean(order.description)}")
    if order.slot:
        lines.append(f"📌 Slot: {_clean(order.slot)}")
    if order.start_date:
        lines.append(f"📅 Ngày đăng ký: {_clean(order.start_date.strftime('%d/%m/%Y'))}")
    if order.duration_days:
        lines.append(f"⏱️ Thời hạn: {order.duration_days} ngày")
    if order.expiry_date:
        lines.append(f"📆 Ngày hết hạn: {_clean(order.expiry_date.strftime('%d/%m/%Y'))}")
    lines.append(f"💰 Giá bán: {_format_currency(order.sale_price)}")

    lines.append("──────🤝 THÔNG TIN KHÁCH HÀNG ──────")
    lines.append(f"👥 Tên: {_clean(order.customer_name or '---')}")
    if order.customer_link:
        lines.append(f"🔗 Liên hệ: {_clean(order.customer_link)}")

    lines.append("──────ℹ️ THÔNG TIN THANH TOÁN ──────")
    lines.append("")
    lines.append("🏦 Ngân hàng: VP Bank")
    lines.append("🏧 STK: 9183400998")
    lines.append("👤 Tên: NGO LE NGOC HUNG")
    lines.append(f"🧾 Nội dung: Thanh toán {_clean(order.order_code)}")

    lines.append("")
    lines.append("⚠️ Vui lòng ghi đúng mã đơn trong nội dung chuyển khoản để xử lý nhanh.")
    lines.append("🙏 Trân trọng cảm ơn quý khách!")
    caption = "\n".join(lines)

    qr_image = None
    if order.sale_price > 0:
        try:
            qr_url = QR_TEMPLATE.format(amount=order.sale_price, order_id=order.order_code)
            response = requests.get(qr_url, timeout=10)
            response.raise_for_status()
            qr_image = BytesIO(response.content)
        except requests.RequestException as exc:
            logger.warning("Failed generating QR for %s: %s", order.order_code, exc)

    return caption, qr_image


async def check_due_orders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running SQL-based due orders job...")
    if not SEND_DUE_ORDER_TO_TOPIC:
        logger.info("SEND_DUE_ORDER_TO_TOPIC is disabled; skipping notification job.")
        return
    try:
        orders = fetch_due_orders()
    except Exception as exc:
        logger.error("Failed to query due orders: %s", exc, exc_info=True)
        if SEND_ERROR_TO_TOPIC and ERROR_GROUP_ID and ERROR_TOPIC_ID is not None:
            try:
                await context.bot.send_message(
                    chat_id=ERROR_GROUP_ID,
                    message_thread_id=ERROR_TOPIC_ID,
                    text=f"Job view_due_orders gap loi SQL: `{exc}`",
                )
            except Exception:
                pass
        return

    group_id = DUE_ORDER_GROUP_ID
    topic_id = DUE_ORDER_TOPIC_ID
    if not group_id or not topic_id:
        logger.error("Missing DUE_ORDER_GROUP_ID or DUE_ORDER_TOPIC_ID in config.")
        return

    if not orders:
        logger.info("No due orders (days_left=%s).", TARGET_DAYS_LEFT)
        try:
            await context.bot.send_message(
                chat_id=group_id,
                message_thread_id=topic_id,
                text=escape_mdv2("Không có đơn nào cần gia hạn."),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as exc:
            logger.error("Failed sending empty notification: %s", exc)
        return

    try:
        await context.bot.send_message(
            chat_id=group_id,
            message_thread_id=topic_id,
            text=escape_mdv2(
                f"Thông Báo: Tìm Thấy {len(orders)} đơn cần gia hạn."
            ),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except Exception as exc:
        logger.warning("Failed sending header message: %s", exc)

    for index, order in enumerate(orders):
        caption, qr_image = _build_caption_pretty(order, index, len(orders))
        try:
            if qr_image:
                qr_image.seek(0)
                await context.bot.send_photo(
                    chat_id=group_id,
                    message_thread_id=topic_id,
                    photo=qr_image,
                    caption=caption,
                    parse_mode=None,
                )
            else:
                await context.bot.send_message(
                    chat_id=group_id,
                    message_thread_id=topic_id,
                    text=caption,
                    parse_mode=None,
                )
        except BadRequest as exc:
            logger.error("Failed sending order %s: %s", order.order_code, exc)
        except Exception as exc:
            logger.error("Unexpected error sending order %s: %s", order.order_code, exc, exc_info=True)


def _format_due_orders_console(orders: list[DueOrder]) -> str:
    parts = []
    for order in orders:
        parts.append(
            f"{order.order_code} | {order.product_name} | {order.customer_name} | "
            f"days_left={order.days_left} | price={order.sale_price}"
        )
    return "\n".join(parts)


def test_view_due_orders(limit: int = 5) -> None:
    """
    Quick manual test helper so we can run `python -m mavrykbot.handlers.view_due_orders`.
    Prints a summary of the due orders fetched from the database.
    """
    logger.info("Running manual test for view_due_orders with limit=%s", limit)
    orders = fetch_due_orders(limit=limit)
    if not orders:
        print("No due orders found.")
        return
    print(_format_due_orders_console(orders))

async def _safe_reply(update: Update, text: str, *, markdown: bool = False) -> None:
    """Send a reply, swallowing temporary network errors."""
    if update.message is None:
        return
    try:
        await update.message.reply_text(
            text if not markdown else escape_mdv2(text),
            parse_mode=ParseMode.MARKDOWN_V2 if markdown else None,
        )
    except (TimedOut, NetworkError) as exc:
        logger.warning("Telegram timeout while replying: %s", exc)
    except Exception as exc:  # pragma: no cover - extra safety
        logger.error("Failed to send reply: %s", exc, exc_info=True)


async def test_due_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/testjob: kích hoạt thủ công job thông báo 7:00 sáng (giả lập chạy ngay)."""
    if update.message is None:
        return

    await _safe_reply(
        update,
        "Đang kích hoạt giả lập job 7:00 sáng. Vui lòng kiểm tra group/thảo luận thông báo.",
        markdown=True,
    )

    try:
        await check_due_orders_job(context)
        await _safe_reply(update, "Job 7:00 đã chạy xong (giả lập). Kiểm tra group đã cấu hình.", markdown=True)
    except Exception as exc:
        logger.error("Lỗi khi chạy test job (giả lập 7h): %s", exc, exc_info=True)
        await _safe_reply(update, f"Lỗi khi chạy job: {exc}", markdown=True)
