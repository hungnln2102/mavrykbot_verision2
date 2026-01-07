"""Constants for PostgreSQL tables/columns across schemas (mavryk/orders/product/partner)."""
from __future__ import annotations

import os
from typing import Final, Mapping


def _table(schema: str | None, name: str) -> str:
    return f"{schema}.{name}" if schema else name


# Schema names (override via environment to match the running DB)
SCHEMA: Final[str] = os.getenv("DB_SCHEMA", "mavryk")
SCHEMA_ORDERS: Final[str] = os.getenv("DB_SCHEMA_ORDERS", "orders")
SCHEMA_PRODUCT: Final[str] = os.getenv("DB_SCHEMA_PRODUCT", "product")
SCHEMA_PARTNER: Final[str] = os.getenv("DB_SCHEMA_PARTNER", "partner")

PAYMENT_RECEIPT_TABLE: Final[str] = _table(SCHEMA, "payment_receipt")
class PaymentReceiptColumns:
    ID: Final[str] = "id"
    MA_DON_HANG: Final[str] = "id_order"
    NGAY_THANH_TOAN: Final[str] = "payment_date"
    SO_TIEN: Final[str] = "amount"
    RECEIVER: Final[str] = "receiver"
    NGUOI_GUI: Final[str] = "sender"
    NOI_DUNG_CK: Final[str] = "note"

PAYMENT_SUPPLY_TABLE: Final[str] = _table(SCHEMA, "payment_supply")
class PaymentSupplyColumns:
    ID: Final[str] = "id"
    SOURCE_ID: Final[str] = "source_id"
    IMPORT: Final[str] = "import"
    ROUND: Final[str] = "round"
    STATUS: Final[str] = "status"
    PAID: Final[str] = "paid"

# ----------------------------
# Orders schema (SCHEMA_ORDERS)
# ----------------------------
ORDER_LIST_TABLE: Final[str] = _table(SCHEMA_ORDERS, "order_list")
class OrderListColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_order"
    SAN_PHAM: Final[str] = "id_product"
    THONG_TIN_SAN_PHAM: Final[str] = "information_order"
    KHACH_HANG: Final[str] = "customer"
    LINK_LIEN_HE: Final[str] = "contact"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "order_date"
    SO_NGAY_DA_DANG_KI: Final[str] = "days"
    HET_HAN: Final[str] = "order_expired"
    NGUON: Final[str] = "supply"
    GIA_NHAP: Final[str] = "cost"
    GIA_BAN: Final[str] = "price"
    NOTE: Final[str] = "note"
    TINH_TRANG: Final[str] = "status"
    CHECK_FLAG: Final[str] = "check_flag"

ORDER_EXPIRED_TABLE: Final[str] = _table(SCHEMA_ORDERS, "order_expired")
class OrderExpiredColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_order"
    SAN_PHAM: Final[str] = "id_product"
    THONG_TIN_SAN_PHAM: Final[str] = "information_order"
    KHACH_HANG: Final[str] = "customer"
    LINK_LIEN_HE: Final[str] = "contact"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "order_date"
    SO_NGAY_DA_DANG_KI: Final[str] = "days"
    HET_HAN: Final[str] = "order_expired"
    NGUON: Final[str] = "supply"
    GIA_NHAP: Final[str] = "cost"
    GIA_BAN: Final[str] = "price"
    NOTE: Final[str] = "note"
    TINH_TRANG: Final[str] = "status"
    CHECK_FLAG: Final[str] = "check_flag"
    ARCHIVED_AT: Final[str] = "archived_at"

ORDER_CANCELED_TABLE: Final[str] = _table(SCHEMA_ORDERS, "order_canceled")
class OrderCanceledColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_order"
    SAN_PHAM: Final[str] = "id_product"
    THONG_TIN_SAN_PHAM: Final[str] = "information_order"
    KHACH_HANG: Final[str] = "customer"
    LINK_LIEN_HE: Final[str] = "contact"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "order_date"
    SO_NGAY_DA_DANG_KI: Final[str] = "days"
    HET_HAN: Final[str] = "order_expired"
    NGUON: Final[str] = "supply"
    GIA_NHAP: Final[str] = "cost"
    GIA_BAN: Final[str] = "price"
    NOTE: Final[str] = "note"
    TINH_TRANG: Final[str] = "status"
    CHECK_FLAG: Final[str] = "check_flag"
    CAN_HOAN: Final[str] = "refund"
    REFUND: Final[str] = CAN_HOAN
    CREATE_DATE: Final[str] = "createdate"

# ----------------------------
PRODUCT_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "product")
class ProductColumns:
    ID: Final[str] = "id"
    CATEGORY_ID: Final[str] = "category_id"
    PACKAGE_NAME: Final[str] = "package_name"

PRICE_CONFIG_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "price_config")
class PriceConfigColumns:
    ID: Final[str] = "id"
    VARIANT_ID: Final[str] = "variant_id"
    PCT_CTV: Final[str] = "pct_ctv"
    PCT_KHACH: Final[str] = "pct_khach"
    PCT_PROMO: Final[str] = "pct_promo"
    UPDATED_AT: Final[str] = "updated_at"

# Keep the raw variant table reference for direct queries when needed.
VARIANT_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "variant")
class VariantColumns:
    ID: Final[str] = "id"
    PRODUCT_ID: Final[str] = "product_id"
    VARIANT_NAME: Final[str] = "variant_name"
    IS_ACTIVE: Final[str] = "is_active"
    DISPLAY_NAME: Final[str] = "display_name"
    PACKAGE_NAME: Final[str] = "package_name"  # join from product if selected

# ----------------------------
# Partner schema (SCHEMA_PARTNER)
# ----------------------------
SUPPLIER_TABLE: Final[str] = _table(SCHEMA_PARTNER, "supplier")
SUPPLY_TABLE: Final[str] = SUPPLIER_TABLE
class SupplyColumns:
    ID: Final[str] = "id"
    SOURCE_NAME: Final[str] = "supplier_name"
    SUPPLIER_NAME: Final[str] = SOURCE_NAME
    NUMBER_BANK: Final[str] = "number_bank"
    BIN_BANK: Final[str] = "bin_bank"
    ACTIVE_SUPPLY: Final[str] = "active_supply"

SUPPLIER_COST_TABLE: Final[str] = _table(SCHEMA_PARTNER, "supplier_cost")
SUPPLY_PRICE_TABLE: Final[str] = SUPPLIER_COST_TABLE
class SupplyPriceColumns:
    ID: Final[str] = "id"
    PRODUCT_ID: Final[str] = "product_id"
    SOURCE_ID: Final[str] = "supplier_id"
    SUPPLIER_ID: Final[str] = SOURCE_ID
    PRICE: Final[str] = "price"


COLUMNS: Final[Mapping[str, Mapping[str, str]]] = {
    "order_canceled": {
        "ID": OrderCanceledColumns.ID,
        "ID_DON_HANG": OrderCanceledColumns.ID_DON_HANG,
        "SAN_PHAM": OrderCanceledColumns.SAN_PHAM,
        "THONG_TIN_SAN_PHAM": OrderCanceledColumns.THONG_TIN_SAN_PHAM,
        "KHACH_HANG": OrderCanceledColumns.KHACH_HANG,
        "LINK_LIEN_HE": OrderCanceledColumns.LINK_LIEN_HE,
        "SLOT": OrderCanceledColumns.SLOT,
        "NGAY_DANG_KI": OrderCanceledColumns.NGAY_DANG_KI,
        "SO_NGAY_DA_DANG_KI": OrderCanceledColumns.SO_NGAY_DA_DANG_KI,
        "HET_HAN": OrderCanceledColumns.HET_HAN,
        "NGUON": OrderCanceledColumns.NGUON,
        "GIA_NHAP": OrderCanceledColumns.GIA_NHAP,
        "GIA_BAN": OrderCanceledColumns.GIA_BAN,
        "NOTE": OrderCanceledColumns.NOTE,
        "TINH_TRANG": OrderCanceledColumns.TINH_TRANG,
        "CHECK_FLAG": OrderCanceledColumns.CHECK_FLAG,
        "CAN_HOAN": OrderCanceledColumns.CAN_HOAN,
        "CREATE_DATE": OrderCanceledColumns.CREATE_DATE,
    },
    "order_expired": {
        "ID": OrderExpiredColumns.ID,
        "ID_DON_HANG": OrderExpiredColumns.ID_DON_HANG,
        "SAN_PHAM": OrderExpiredColumns.SAN_PHAM,
        "THONG_TIN_SAN_PHAM": OrderExpiredColumns.THONG_TIN_SAN_PHAM,
        "KHACH_HANG": OrderExpiredColumns.KHACH_HANG,
        "LINK_LIEN_HE": OrderExpiredColumns.LINK_LIEN_HE,
        "SLOT": OrderExpiredColumns.SLOT,
        "NGAY_DANG_KI": OrderExpiredColumns.NGAY_DANG_KI,
        "SO_NGAY_DA_DANG_KI": OrderExpiredColumns.SO_NGAY_DA_DANG_KI,
        "HET_HAN": OrderExpiredColumns.HET_HAN,
        "NGUON": OrderExpiredColumns.NGUON,
        "GIA_NHAP": OrderExpiredColumns.GIA_NHAP,
        "GIA_BAN": OrderExpiredColumns.GIA_BAN,
        "NOTE": OrderExpiredColumns.NOTE,
        "TINH_TRANG": OrderExpiredColumns.TINH_TRANG,
        "CHECK_FLAG": OrderExpiredColumns.CHECK_FLAG,
        "ARCHIVED_AT": OrderExpiredColumns.ARCHIVED_AT,
    },
    "order_list": {
        "ID": OrderListColumns.ID,
        "ID_DON_HANG": OrderListColumns.ID_DON_HANG,
        "SAN_PHAM": OrderListColumns.SAN_PHAM,
        "THONG_TIN_SAN_PHAM": OrderListColumns.THONG_TIN_SAN_PHAM,
        "KHACH_HANG": OrderListColumns.KHACH_HANG,
        "LINK_LIEN_HE": OrderListColumns.LINK_LIEN_HE,
        "SLOT": OrderListColumns.SLOT,
        "NGAY_DANG_KI": OrderListColumns.NGAY_DANG_KI,
        "SO_NGAY_DA_DANG_KI": OrderListColumns.SO_NGAY_DA_DANG_KI,
        "HET_HAN": OrderListColumns.HET_HAN,
        "NGUON": OrderListColumns.NGUON,
        "GIA_NHAP": OrderListColumns.GIA_NHAP,
        "GIA_BAN": OrderListColumns.GIA_BAN,
        "NOTE": OrderListColumns.NOTE,
        "TINH_TRANG": OrderListColumns.TINH_TRANG,
        "CHECK_FLAG": OrderListColumns.CHECK_FLAG,
    },
    "payment_receipt": {
        "ID": PaymentReceiptColumns.ID,
        "MA_DON_HANG": PaymentReceiptColumns.MA_DON_HANG,
        "NGAY_THANH_TOAN": PaymentReceiptColumns.NGAY_THANH_TOAN,
        "SO_TIEN": PaymentReceiptColumns.SO_TIEN,
        "RECEIVER": PaymentReceiptColumns.RECEIVER,
        "NGUOI_GUI": PaymentReceiptColumns.NGUOI_GUI,
        "NOI_DUNG_CK": PaymentReceiptColumns.NOI_DUNG_CK,
    },
    "payment_supply": {
        "ID": PaymentSupplyColumns.ID,
        "SOURCE_ID": PaymentSupplyColumns.SOURCE_ID,
        "IMPORT": PaymentSupplyColumns.IMPORT,
        "ROUND": PaymentSupplyColumns.ROUND,
        "STATUS": PaymentSupplyColumns.STATUS,
        "PAID": PaymentSupplyColumns.PAID,
    },
    "price_config": {
        "ID": PriceConfigColumns.ID,
        "VARIANT_ID": PriceConfigColumns.VARIANT_ID,
        "PCT_CTV": PriceConfigColumns.PCT_CTV,
        "PCT_KHACH": PriceConfigColumns.PCT_KHACH,
        "PCT_PROMO": PriceConfigColumns.PCT_PROMO,
        "UPDATED_AT": PriceConfigColumns.UPDATED_AT,
    },
    "variant": {
        "ID": VariantColumns.ID,
        "PRODUCT_ID": VariantColumns.PRODUCT_ID,
        "VARIANT_NAME": VariantColumns.VARIANT_NAME,
        "IS_ACTIVE": VariantColumns.IS_ACTIVE,
        "DISPLAY_NAME": VariantColumns.DISPLAY_NAME,
        "PACKAGE_NAME": VariantColumns.PACKAGE_NAME,
    },
    "supplier": {
        "ID": SupplyColumns.ID,
        "SUPPLIER_NAME": SupplyColumns.SOURCE_NAME,
        "NUMBER_BANK": SupplyColumns.NUMBER_BANK,
        "BIN_BANK": SupplyColumns.BIN_BANK,
        "ACTIVE_SUPPLY": SupplyColumns.ACTIVE_SUPPLY,
    },
    "supplier_cost": {
        "ID": SupplyPriceColumns.ID,
        "PRODUCT_ID": SupplyPriceColumns.PRODUCT_ID,
        "SUPPLIER_ID": SupplyPriceColumns.SOURCE_ID,
        "PRICE": SupplyPriceColumns.PRICE,
    },
}
