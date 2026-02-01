"""Database query functions for update order."""
import logging
from typing import List, Optional, Sequence

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE,
    PRICE_CONFIG_TABLE,
    SUPPLY_PRICE_TABLE,
    SUPPLY_TABLE,
    VARIANT_TABLE,
    OrderListColumns,
    PriceConfigColumns,
    SupplyColumns,
    SupplyPriceColumns,
    VariantColumns,
)
from mavrykbot.handlers.UpdateOrder.models import ORDER_SELECT_FIELDS, OrderRecord
from mavrykbot.handlers.UpdateOrder.utils import _build_order

logger = logging.getLogger(__name__)


def query_orders_by_id(search_term: str) -> List[OrderRecord]:
    sql = f"""
        SELECT {", ".join(ORDER_SELECT_FIELDS)}
        FROM {ORDER_LIST_TABLE}
        WHERE LOWER({OrderListColumns.ID_DON_HANG}) = LOWER(%s)
        ORDER BY {OrderListColumns.ID} DESC
    """
    rows = db.fetch_all(sql, (search_term.strip(),))
    return [_build_order(row) for row in rows]


def query_orders_by_info(search_term: str) -> List[OrderRecord]:
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


def lookup_product_profile(product_name: str) -> Optional[Sequence]:
    sql = f"""
        SELECT v.{VariantColumns.ID},
               pc.{PriceConfigColumns.PCT_CTV},
               pc.{PriceConfigColumns.PCT_KHACH},
               pc.{PriceConfigColumns.PCT_PROMO}
        FROM {VARIANT_TABLE} v
        LEFT JOIN {PRICE_CONFIG_TABLE} pc
            ON pc.{PriceConfigColumns.VARIANT_ID} = v.{VariantColumns.ID}
        WHERE LOWER(v.{VariantColumns.DISPLAY_NAME}) = LOWER(%s)
        LIMIT 1
    """
    return db.fetch_one(sql, (product_name.strip(),))


def lookup_source_price(product_id: int, source_name: str) -> Optional[int]:
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


def lookup_highest_price(product_id: int) -> int:
    sql = f"""
        SELECT MAX({SupplyPriceColumns.PRICE})
        FROM {SUPPLY_PRICE_TABLE}
        WHERE {SupplyPriceColumns.PRODUCT_ID} = %s
    """
    row = db.fetch_one(sql, (product_id,))
    return int(row[0]) if row and row[0] else 0


def check_source_exists(source_name: str) -> bool:
    sql = f"""
        SELECT 1 FROM {SUPPLY_TABLE}
        WHERE LOWER({SupplyColumns.SOURCE_NAME}) = LOWER(%s)
        LIMIT 1
    """
    return db.fetch_one(sql, (source_name,)) is not None
