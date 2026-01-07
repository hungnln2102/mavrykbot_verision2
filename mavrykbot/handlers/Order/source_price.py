import logging
from decimal import Decimal
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    PRICE_CONFIG_TABLE,
    VARIANT_TABLE,
    PriceConfigColumns,
    VariantColumns,
)

from .calculate_price import calculate_sale_price
from .states import STATE_CHON_NGUON, STATE_NHAP_GIA_NHAP, STATE_NHAP_NGUON_MOI, STATE_NHAP_THONG_TIN
from .utils import _parse_price, _round_thousand, safe_edit_md
from .finalize import end_add

logger = logging.getLogger(__name__)


async def chon_nguon_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 1)
    if len(parts) < 2:
        logger.warning("Received unexpected callback_data format in chon_nguon_handler: %s", query.data)
        await safe_edit_md(context.bot, query.message.chat.id, query.message.message_id, "❌ Đã xảy ra lỗi, vui lòng thử lại từ đầu.")
        return await end_add(update, context, success=False)

    nguon = parts[1].strip()
    context.user_data["nguon"] = nguon

    product_id = context.user_data.get("product_id")
    source_price_map = context.user_data.get("source_price_map", {})
    max_supply_price = context.user_data.get("max_supply_price")
    ma_don = context.user_data.get("ma_don", "")

    # 1. Giá nhập hiển thị lấy theo nguồn đã chọn (phục vụ lưu trữ), nhưng tính bán dùng giá cao nhất.
    gia_nhap = source_price_map.get(nguon, 0)
    context.user_data["gia_nhap_value"] = gia_nhap
    logger.info("LOG_PRICE_CALC | Selected source '%s' input price: %s", nguon, gia_nhap)

    # Base để tính giá bán: luôn dùng giá cao nhất trong supply_price theo product (nếu có).
    if max_supply_price is not None:
        try:
            price_value = Decimal(str(max_supply_price))
        except Exception:
            price_value = Decimal(str(gia_nhap))
    else:
        price_value = Decimal(str(gia_nhap))

    try:
        # 2. Lấy hệ số PCT từ bảng Product_Price cho sản phẩm đang chọn
        pct_ctv = Decimal("1.0")
        pct_khach = Decimal("1.0")
        pct_promo = Decimal("0")
        if product_id:
            percentages_query = f"""
                SELECT pc.{PriceConfigColumns.PCT_CTV},
                       pc.{PriceConfigColumns.PCT_KHACH},
                       pc.{PriceConfigColumns.PCT_PROMO}
                FROM {PRICE_CONFIG_TABLE} AS pc
                WHERE pc.{PriceConfigColumns.VARIANT_ID} = %s
            """
            percentages_result = db.fetch_one(percentages_query, (product_id,))
            if percentages_result:
                pct_ctv_raw, pct_khach_raw, pct_promo_raw = percentages_result
                pct_ctv = Decimal(str(pct_ctv_raw)) if pct_ctv_raw is not None else Decimal("1.0")
                pct_khach = Decimal(str(pct_khach_raw)) if pct_khach_raw is not None else Decimal("1.0")
                pct_promo = Decimal(str(pct_promo_raw)) if pct_promo_raw is not None else Decimal("0")
        logger.info(
            "LOG_PRICE_CALC | Percentages - PCT_CTV: %s, PCT_KHACH: %s, PCT_PROMO: %s",
            pct_ctv,
            pct_khach,
            pct_promo,
        )

        logger.info("LOG_PRICE_CALC | Base price (max supply price or input): %s", price_value)

        gia_ban = calculate_sale_price(
            ma_don,
            price_value,
            pct_ctv=pct_ctv,
            pct_khach=pct_khach,
            pct_promo=pct_promo,
            gia_nhap=gia_nhap,
        )
        logger.info("LOG_PRICE_CALC | Final calculated price (integer): %s", gia_ban)

    except Exception as e:
        logger.error("Lỗi khi tính giá bán theo logic mới: %s", e)
        # Trong trường hợp lỗi, giá bán sẽ là giá nhập
        gia_ban = _round_thousand(gia_nhap)
        logger.info("LOG_PRICE_CALC | Exception fallback: final_price = input_price = %s", gia_ban)

    context.user_data["gia_ban_value"] = gia_ban
    logger.info("LOG_PRICE_CALC | Final calculated price (integer): %s", gia_ban)

    await safe_edit_md(
        context.bot,
        query.message.chat.id,
        query.message.message_id,
        text="📝 Vui lòng nhập *Thông tin đơn hàng*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]),
    )
    return STATE_NHAP_THONG_TIN


async def chon_nguon_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await safe_edit_md(
        context.bot, query.message.chat.id, query.message.message_id,
        text="🚚 Vui lòng nhập *tên Nguồn hàng mới*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]),
    )
    return STATE_NHAP_NGUON_MOI


async def nhap_nguon_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nguon"] = update.message.text.strip()
    await update.message.delete()
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data["main_message_id"],
        text="💰 Vui lòng nhập *Giá nhập*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]),
    )
    return STATE_NHAP_GIA_NHAP


async def nhap_gia_nhap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gia_nhap_raw = update.message.text.strip()
    await update.message.delete()

    gia_nhap_value = _parse_price(gia_nhap_raw)

    if gia_nhap_value < 0:
        await safe_edit_md(
            context.bot,
            update.effective_chat.id,
            context.user_data["main_message_id"],
            text="⚠️ Giá nhập không hợp lệ. Vui lòng chỉ nhập số:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]),
        )
        return STATE_NHAP_GIA_NHAP

    context.user_data["gia_nhap_value"] = gia_nhap_value

    await safe_edit_md(
        context.bot,
        update.effective_chat.id,
        context.user_data["main_message_id"],
        text="📝 Vui lòng nhập *Thông tin đơn hàng*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]),
    )
    return STATE_NHAP_THONG_TIN
