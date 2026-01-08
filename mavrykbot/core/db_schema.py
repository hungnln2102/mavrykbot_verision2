"""Constants for PostgreSQL tables/columns across schemas (orders/product/supplier)."""
from __future__ import annotations

import os
from typing import Final, Mapping


def _table(schema: str | None, name: str) -> str:
    return f"{schema}.{name}" if schema else name


def _pick_schema(*candidates: str | None) -> str:
    for candidate in candidates:
        if candidate:
            return candidate
    return ""


# Schema names (override via environment to match the running DB)
SCHEMA_ORDERS: Final[str] = _pick_schema(
    os.getenv("DB_SCHEMA_ORDERS"), os.getenv("SCHEMA_ORDERS"), "orders"
)
SCHEMA_PRODUCT: Final[str] = _pick_schema(
    os.getenv("DB_SCHEMA_PRODUCT"), os.getenv("SCHEMA_PRODUCT"), "product"
)
SCHEMA_PARTNER: Final[str] = _pick_schema(
    os.getenv("DB_SCHEMA_PARTNER"), os.getenv("SCHEMA_PARTNER"), "partner"
)
SCHEMA_SUPPLIER: Final[str] = _pick_schema(
    os.getenv("DB_SCHEMA_SUPPLIER"), SCHEMA_PARTNER, SCHEMA_PRODUCT
)
SCHEMA_SUPPLIER_COST: Final[str] = _pick_schema(
    os.getenv("DB_SCHEMA_SUPPLIER_COST"), SCHEMA_PRODUCT, SCHEMA_PARTNER
)


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


PAYMENT_RECEIPT_TABLE: Final[str] = _table(SCHEMA_ORDERS, "payment_receipt")


class PaymentReceiptColumns:
    ID: Final[str] = "id"
    ORDER_CODE: Final[str] = "id_order"
    PAID_DATE: Final[str] = "payment_date"
    AMOUNT: Final[str] = "amount"
    RECEIVER: Final[str] = "receiver"
    NOTE: Final[str] = "note"
    SENDER: Final[str] = "sender"
    MA_DON_HANG: Final[str] = ORDER_CODE
    NGAY_THANH_TOAN: Final[str] = PAID_DATE
    SO_TIEN: Final[str] = AMOUNT
    NGUOI_GUI: Final[str] = SENDER
    NOI_DUNG_CK: Final[str] = NOTE


# -----------------------------
# Product schema (SCHEMA_PRODUCT)
# -----------------------------
PRODUCT_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "product")


class ProductColumns:
    ID: Final[str] = "id"
    CATEGORY_ID: Final[str] = "category_id"
    PACKAGE_NAME: Final[str] = "package_name"


VARIANT_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "variant")


class VariantColumns:
    ID: Final[str] = "id"
    PRODUCT_ID: Final[str] = "product_id"
    VARIANT_NAME: Final[str] = "variant_name"
    IS_ACTIVE: Final[str] = "is_active"
    DISPLAY_NAME: Final[str] = "display_name"


PRICE_CONFIG_TABLE: Final[str] = _table(SCHEMA_PRODUCT, "price_config")


class PriceConfigColumns:
    ID: Final[str] = "id"
    VARIANT_ID: Final[str] = "variant_id"
    PCT_CTV: Final[str] = "pct_ctv"
    PCT_KHACH: Final[str] = "pct_khach"
    PCT_PROMO: Final[str] = "pct_promo"
    UPDATED_AT: Final[str] = "updated_at"


# ----------------------------
# Supplier schema (SCHEMA_SUPPLIER)
# ----------------------------
SUPPLIER_TABLE: Final[str] = _table(SCHEMA_SUPPLIER, "supplier")
SUPPLY_TABLE: Final[str] = SUPPLIER_TABLE


class SupplyColumns:
    ID: Final[str] = "id"
    SOURCE_NAME: Final[str] = "supplier_name"
    SUPPLIER_NAME: Final[str] = SOURCE_NAME
    NUMBER_BANK: Final[str] = "number_bank"
    BIN_BANK: Final[str] = "bin_bank"
    ACTIVE_SUPPLY: Final[str] = "active_supply"


SUPPLIER_PAYMENTS_TABLE: Final[str] = _table(SCHEMA_SUPPLIER, "supplier_payments")
PAYMENT_SUPPLY_TABLE: Final[str] = SUPPLIER_PAYMENTS_TABLE


class PaymentSupplyColumns:
    ID: Final[str] = "id"
    SUPPLIER_ID: Final[str] = "supplier_id"
    TOTAL_AMOUNT: Final[str] = "total_amount"
    PAYMENT_PERIOD: Final[str] = "payment_period"
    PAYMENT_STATUS: Final[str] = "payment_status"
    AMOUNT_PAID: Final[str] = "amount_paid"
    SOURCE_ID: Final[str] = SUPPLIER_ID
    IMPORT: Final[str] = TOTAL_AMOUNT
    ROUND: Final[str] = PAYMENT_PERIOD
    STATUS: Final[str] = PAYMENT_STATUS
    PAID: Final[str] = AMOUNT_PAID


# Cost per supplier stored in supplier_cost (schema varies by environment)
SUPPLIER_COST_TABLE: Final[str] = _table(SCHEMA_SUPPLIER_COST, "supplier_cost")
SUPPLY_PRICE_TABLE: Final[str] = SUPPLIER_COST_TABLE


class SupplyPriceColumns:
    ID: Final[str] = "id"
    PRODUCT_ID: Final[str] = "product_id"
    SOURCE_ID: Final[str] = "supplier_id"
    SUPPLIER_ID: Final[str] = SOURCE_ID
    PRICE: Final[str] = "price"


COLUMNS: Final[Mapping[str, Mapping[str, str]]] = {
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
        "ORDER_CODE": PaymentReceiptColumns.ORDER_CODE,
        "PAID_DATE": PaymentReceiptColumns.PAID_DATE,
        "AMOUNT": PaymentReceiptColumns.AMOUNT,
        "RECEIVER": PaymentReceiptColumns.RECEIVER,
        "NOTE": PaymentReceiptColumns.NOTE,
        "SENDER": PaymentReceiptColumns.SENDER,
    },
    "product": {
        "ID": ProductColumns.ID,
        "CATEGORY_ID": ProductColumns.CATEGORY_ID,
        "PACKAGE_NAME": ProductColumns.PACKAGE_NAME,
    },
    "variant": {
        "ID": VariantColumns.ID,
        "PRODUCT_ID": VariantColumns.PRODUCT_ID,
        "VARIANT_NAME": VariantColumns.VARIANT_NAME,
        "IS_ACTIVE": VariantColumns.IS_ACTIVE,
        "DISPLAY_NAME": VariantColumns.DISPLAY_NAME,
    },
    "price_config": {
        "ID": PriceConfigColumns.ID,
        "VARIANT_ID": PriceConfigColumns.VARIANT_ID,
        "PCT_CTV": PriceConfigColumns.PCT_CTV,
        "PCT_KHACH": PriceConfigColumns.PCT_KHACH,
        "PCT_PROMO": PriceConfigColumns.PCT_PROMO,
        "UPDATED_AT": PriceConfigColumns.UPDATED_AT,
    },
    "supplier": {
        "ID": SupplyColumns.ID,
        "SUPPLIER_NAME": SupplyColumns.SOURCE_NAME,
        "NUMBER_BANK": SupplyColumns.NUMBER_BANK,
        "BIN_BANK": SupplyColumns.BIN_BANK,
        "ACTIVE_SUPPLY": SupplyColumns.ACTIVE_SUPPLY,
    },
    "supplier_payments": {
        "ID": PaymentSupplyColumns.ID,
        "SUPPLIER_ID": PaymentSupplyColumns.SUPPLIER_ID,
        "TOTAL_AMOUNT": PaymentSupplyColumns.TOTAL_AMOUNT,
        "PAYMENT_PERIOD": PaymentSupplyColumns.PAYMENT_PERIOD,
        "PAYMENT_STATUS": PaymentSupplyColumns.PAYMENT_STATUS,
        "AMOUNT_PAID": PaymentSupplyColumns.AMOUNT_PAID,
    },
    "supplier_cost": {
        "ID": SupplyPriceColumns.ID,
        "PRODUCT_ID": SupplyPriceColumns.PRODUCT_ID,
        "SUPPLIER_ID": SupplyPriceColumns.SOURCE_ID,
        "PRICE": SupplyPriceColumns.PRICE,
    },
}
