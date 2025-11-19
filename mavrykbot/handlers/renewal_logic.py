"""Renewal logic that works directly with the SQL order_list table."""
from __future__ import annotations

import logging
import re
from datetime import date as date_type, datetime, timedelta
from decimal import Decimal

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    OrderListColumns,
    PRODUCT_PRICE_TABLE,
    ProductPriceColumns,
    SUPPLY_TABLE,
    SupplyColumns,
    SUPPLY_PRICE_TABLE,
    SupplyPriceColumns,
)
from mavrykbot.core.utils import chuan_hoa_gia, normalize_product_duration

logger = logging.getLogger(__name__)

DATE_FMT = "%d/%m/%Y"
DB_DATE_FMT = "%Y/%m/%d"


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date_type):
        return datetime.combine(value, datetime.min.time())
    value_str = str(value).strip()
    for fmt in (DATE_FMT, "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value_str, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(value_str)
    except Exception:
        return None


def _format_date(dt: datetime) -> str:
    return dt.strftime(DATE_FMT)


def _format_db_date(dt: datetime) -> str:
    return dt.strftime(DB_DATE_FMT)


def tinh_ngay_het_han(ngay_dang_ky_str: str, so_ngay_str: str) -> str:
    start = _parse_date(ngay_dang_ky_str)
    if not start:
        return ""
    try:
        num_days = int(so_ngay_str)
    except (TypeError, ValueError):
        return ""
    end_date = start + timedelta(days=num_days)
    return _format_date(end_date)


def _fetch_order(order_id: str):
    query = f"""
        SELECT
            {OrderListColumns.SAN_PHAM},
            {OrderListColumns.HET_HAN},
            {OrderListColumns.NGUON},
            {OrderListColumns.GIA_NHAP},
            {OrderListColumns.GIA_BAN},
            {OrderListColumns.THONG_TIN_SAN_PHAM},
            {OrderListColumns.SLOT},
            {OrderListColumns.NGAY_DANG_KI},
            {OrderListColumns.TINH_TRANG},
            {OrderListColumns.CHECK_FLAG}
        FROM {ORDER_LIST_TABLE}
        WHERE {OrderListColumns.ID_DON_HANG} = %s
    """
    return db.fetch_one(query, (order_id,))


def _get_product_record(san_pham: str):
    query = f"""
        SELECT {ProductPriceColumns.ID}, {ProductPriceColumns.PCT_CTV}, {ProductPriceColumns.PCT_KHACH}
        FROM {PRODUCT_PRICE_TABLE}
        WHERE LOWER({ProductPriceColumns.SAN_PHAM}) = LOWER(%s)
        LIMIT 1
    """
    return db.fetch_one(query, (san_pham,))


def _get_source_id(source_name: str | None):
    if not source_name:
        return None
    query = f"""
        SELECT {SupplyColumns.ID}
        FROM {SUPPLY_TABLE}
        WHERE LOWER({SupplyColumns.SOURCE_NAME}) = LOWER(%s)
        LIMIT 1
    """
    res = db.fetch_one(query, (source_name,))
    return res[0] if res else None


def _get_source_price(product_id, source_id):
    if not (product_id and source_id):
        return None
    query = f"""
        SELECT {SupplyPriceColumns.PRICE}
        FROM {SUPPLY_PRICE_TABLE}
        WHERE {SupplyPriceColumns.PRODUCT_ID} = %s AND {SupplyPriceColumns.SOURCE_ID} = %s
        LIMIT 1
    """
    res = db.fetch_one(query, (product_id, source_id))
    price = res[0] if res else None
    return int(price) if price is not None else None


def _get_highest_price(product_id):
    if not product_id:
        return None
    query = f"""
        SELECT MAX({SupplyPriceColumns.PRICE})
        FROM {SUPPLY_PRICE_TABLE}
        WHERE {SupplyPriceColumns.PRODUCT_ID} = %s
    """
    res = db.fetch_one(query, (product_id,))
    price = res[0] if res else None
    return Decimal(price) if price is not None else None


def _calc_gia_ban(order_id: str, highest_price: Decimal | None, pct_ctv: Decimal, pct_khach: Decimal, gia_nhap: int) -> int:
    gia_ban = Decimal(gia_nhap)
    ma = order_id.upper()
    try:
        if highest_price and highest_price > 0:
            if ma.startswith("MAVC"):
                gia_ban = highest_price * pct_ctv
            elif ma.startswith("MAVL"):
                gia_ctv = highest_price * pct_ctv
                gia_ban = gia_ctv * pct_khach
        if ma.startswith("MAVK"):
            gia_ban = Decimal(gia_nhap)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Lỗi khi tính giá bán cho %s", order_id)
        gia_ban = Decimal(gia_nhap)
    return int(((int(gia_ban) + 999) // 1000) * 1000)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "t", "1", "yes"}
    return bool(value)


def _round_to_thousands(value: int | Decimal) -> int:
    numeric = int(Decimal(value))
    if numeric == 0:
        return 0
    remainder = numeric % 1000
    if remainder == 0:
        return numeric
    return numeric + (1000 - remainder) if remainder >= 500 else numeric - remainder


def _update_order(
    order_id: str,
    ngay_dang_ky: str,
    so_ngay: int,
    ngay_het_han: str,
    gia_nhap: int,
    gia_ban: int,
    status: str,
    check_flag: bool,
):
    sql = f"""
        UPDATE {ORDER_LIST_TABLE}
        SET
            {OrderListColumns.NGAY_DANG_KI} = %s,
            {OrderListColumns.SO_NGAY_DA_DANG_KI} = %s,
            {OrderListColumns.HET_HAN} = %s,
            {OrderListColumns.GIA_NHAP} = %s,
            {OrderListColumns.GIA_BAN} = %s,
            {OrderListColumns.TINH_TRANG} = %s,
            {OrderListColumns.CHECK_FLAG} = %s
        WHERE {OrderListColumns.ID_DON_HANG} = %s
    """
    db.execute(sql, (ngay_dang_ky, str(so_ngay), ngay_het_han, gia_nhap, gia_ban, status, check_flag, order_id))


def run_renewal(order_id: str):
    """
    Renew an order if it will expire in <= 4 days.

    Returns tuple (success: bool, details: str|dict, process_type: str)
    """
    if not order_id:
        return False, "Mã đơn hàng không được để trống.", "error"

    order_row = _fetch_order(order_id)
    if not order_row:
        logger.warning("Không tìm thấy đơn hàng %s trong order_list.", order_id)
        return False, f"Không tìm thấy đơn hàng {order_id}", "error"

    (
        san_pham,
        ngay_het_han_str,
        nguon_hang,
        gia_nhap_cu,
        gia_ban_cu,
        thong_tin_sp,
        slot,
        ngay_dang_ky_cu,
        tinh_trang,
        check_flag,
    ) = order_row

    het_han_dt = _parse_date(ngay_het_han_str or "")
    if not het_han_dt:
        return False, f"Ngày hết hạn không hợp lệ cho đơn {order_id}", "error"

    today = datetime.now()
    so_ngay_con_lai = (het_han_dt - today).days
    if so_ngay_con_lai > 4:
        logger.info("Đơn %s còn %s ngày, bỏ qua.", order_id, so_ngay_con_lai)
        return False, "Bỏ qua do còn nhiều ngày", "skipped"

    san_pham_norm = normalize_product_duration(san_pham or "")
    match_thoi_han = re.search(r"--\s*(\d+)\s*m", san_pham_norm, flags=re.I)
    if not match_thoi_han:
        return False, f"Không thể xác định thời hạn từ sản phẩm '{san_pham}'.", "error"

    so_thang = int(match_thoi_han.group(1))
    so_ngay_gia_han = 365 if so_thang == 12 else so_thang * 30

    product_record = _get_product_record(san_pham or "")
    product_id = pct_ctv = pct_khach = None
    if product_record:
        product_id = product_record[0]
        pct_ctv = Decimal(str(product_record[1])) if product_record[1] is not None else Decimal("1.0")
        pct_khach = Decimal(str(product_record[2])) if product_record[2] is not None else Decimal("1.0")
    else:
        pct_ctv = pct_khach = Decimal("1.0")

    source_id = _get_source_id(nguon_hang)
    gia_nhap_source = _get_source_price(product_id, source_id)
    final_gia_nhap = gia_nhap_source if gia_nhap_source is not None else chuan_hoa_gia(gia_nhap_cu)[1]

    highest_price = _get_highest_price(product_id)
    final_gia_ban = _calc_gia_ban(order_id, highest_price, pct_ctv, pct_khach, final_gia_nhap)

    final_gia_nhap = _round_to_thousands(final_gia_nhap)
    final_gia_ban = _round_to_thousands(final_gia_ban)

    ngay_bat_dau_moi_dt = het_han_dt + timedelta(days=1)
    ngay_bat_dau_moi = _format_date(ngay_bat_dau_moi_dt)
    ngay_bat_dau_moi_db = _format_db_date(ngay_bat_dau_moi_dt)
    ngay_het_han_moi = tinh_ngay_het_han(ngay_bat_dau_moi, str(so_ngay_gia_han))
    ngay_het_han_moi_dt = _parse_date(ngay_het_han_moi) or (ngay_bat_dau_moi_dt + timedelta(days=so_ngay_gia_han))
    ngay_het_han_moi_db = _format_db_date(ngay_het_han_moi_dt)

    new_status = "Chưa Thanh Toán"
    new_check_flag = False

    try:
        _update_order(
            order_id,
            ngay_bat_dau_moi_db,
            so_ngay_gia_han,
            ngay_het_han_moi_db,
            final_gia_nhap,
            final_gia_ban,
            new_status,
            new_check_flag,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Không thể cập nhật đơn %s: %s", order_id, exc)
        return False, f"Lỗi cập nhật database: {exc}", "error"

    updated_details = {
        "ID_DON_HANG": order_id,
        "SAN_PHAM": san_pham,
        "THONG_TIN_DON": thong_tin_sp,
        "SLOT": slot,
        "NGAY_DANG_KY": ngay_bat_dau_moi,
        "HET_HAN": ngay_het_han_moi,
        "NGUON": nguon_hang,
        "GIA_NHAP": final_gia_nhap,
        "GIA_BAN": final_gia_ban,
        "TINH_TRANG": new_status,
    }
    logger.info("Gia hạn thành công đơn %s.", order_id)
    return True, updated_details, "renewal"
