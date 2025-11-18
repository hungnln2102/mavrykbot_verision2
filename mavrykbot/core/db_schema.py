"""Constants for PostgreSQL tables/columns in schema "mavryk"."""
from __future__ import annotations

from typing import Final, Mapping

SCHEMA: Final[str] = "mavryk"

ACCOUNT_STORAGE_TABLE: Final[str] = f"{SCHEMA}.account_storage"
class AccountStorageColumns:
    ID: Final[str] = "id"
    USERNAME: Final[str] = "username"
    PASSWORD: Final[str] = "password"
    MAIL_2ND: Final[str] = "Mail 2nd"
    NOTE: Final[str] = "note"
    STORAGE: Final[str] = "storage"
    MAIL_FAMILY: Final[str] = "Mail Family"

BANK_LIST_TABLE: Final[str] = f"{SCHEMA}.bank_list"
class BankListColumns:
    BIN: Final[str] = "bin"
    BANK_NAME: Final[str] = "bank_name"

ORDER_CANCELED_TABLE: Final[str] = f"{SCHEMA}.order_canceled"
class OrderCanceledColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_don_hang"
    SAN_PHAM: Final[str] = "san_pham"
    THONG_TIN_SAN_PHAM: Final[str] = "thong_tin_san_pham"
    KHACH_HANG: Final[str] = "khach_hang"
    LINK_LIEN_HE: Final[str] = "link_lien_he"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "ngay_dang_ki"
    SO_NGAY_DA_DANG_KI: Final[str] = "so_ngay_da_dang_ki"
    HET_HAN: Final[str] = "het_han"
    NGUON: Final[str] = "nguon"
    GIA_NHAP: Final[str] = "gia_nhap"
    GIA_BAN: Final[str] = "gia_ban"
    CAN_HOAN: Final[str] = "can_hoan"
    TINH_TRANG: Final[str] = "tinh_trang"
    CHECK_FLAG: Final[str] = "check_flag"

ORDER_EXPIRED_TABLE: Final[str] = f"{SCHEMA}.order_expired"
class OrderExpiredColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_don_hang"
    SAN_PHAM: Final[str] = "san_pham"
    THONG_TIN_SAN_PHAM: Final[str] = "thong_tin_san_pham"
    KHACH_HANG: Final[str] = "khach_hang"
    LINK_LIEN_HE: Final[str] = "link_lien_he"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "ngay_dang_ki"
    SO_NGAY_DA_DANG_KI: Final[str] = "so_ngay_da_dang_ki"
    HET_HAN: Final[str] = "het_han"
    NGUON: Final[str] = "nguon"
    GIA_NHAP: Final[str] = "gia_nhap"
    GIA_BAN: Final[str] = "gia_ban"
    NOTE: Final[str] = "note"
    TINH_TRANG: Final[str] = "tinh_trang"
    CHECK_FLAG: Final[str] = "check_flag"
    ARCHIVED_AT: Final[str] = "archived_at"

ORDER_LIST_TABLE: Final[str] = f"{SCHEMA}.order_list"
class OrderListColumns:
    ID: Final[str] = "id"
    ID_DON_HANG: Final[str] = "id_don_hang"
    SAN_PHAM: Final[str] = "san_pham"
    THONG_TIN_SAN_PHAM: Final[str] = "thong_tin_san_pham"
    KHACH_HANG: Final[str] = "khach_hang"
    LINK_LIEN_HE: Final[str] = "link_lien_he"
    SLOT: Final[str] = "slot"
    NGAY_DANG_KI: Final[str] = "ngay_dang_ki"
    SO_NGAY_DA_DANG_KI: Final[str] = "so_ngay_da_dang_ki"
    HET_HAN: Final[str] = "het_han"
    NGUON: Final[str] = "nguon"
    GIA_NHAP: Final[str] = "gia_nhap"
    GIA_BAN: Final[str] = "gia_ban"
    NOTE: Final[str] = "note"
    TINH_TRANG: Final[str] = "tinh_trang"
    CHECK_FLAG: Final[str] = "check_flag"

PACKAGE_PRODUCT_TABLE: Final[str] = f"{SCHEMA}.package_product"
class PackageProductColumns:
    ID: Final[str] = "id"
    PACKAGE: Final[str] = "package"
    USERNAME: Final[str] = "username"
    PASSWORD: Final[str] = "password"
    MAIL_2ND: Final[str] = "mail 2nd"
    NOTE: Final[str] = "note"
    EXPIRED: Final[str] = "expired"
    SUPPLIER: Final[str] = "supplier"
    IMPORT: Final[str] = "Import"
    SLOT: Final[str] = "slot"

PAYMENT_RECEIPT_TABLE: Final[str] = f"{SCHEMA}.payment_receipt"
class PaymentReceiptColumns:
    ID: Final[str] = "id"
    MA_DON_HANG: Final[str] = "ma_don_hang"
    NGAY_THANH_TOAN: Final[str] = "ngay_thanh_toan"
    SO_TIEN: Final[str] = "so_tien"
    NGUOI_GUI: Final[str] = "nguoi_gui"
    NOI_DUNG_CK: Final[str] = "noi_dung_ck"

PAYMENT_SUPPLY_TABLE: Final[str] = f"{SCHEMA}.payment_supply"
class PaymentSupplyColumns:
    ID: Final[str] = "id"
    SOURCE_ID: Final[str] = "source_id"
    IMPORT: Final[str] = "import"
    ROUND: Final[str] = "round"
    STATUS: Final[str] = "status"
    PAID: Final[str] = "paid"

PRODUCT_PRICE_TABLE: Final[str] = f"{SCHEMA}.product_price"
class ProductPriceColumns:
    ID: Final[str] = "id"
    SAN_PHAM: Final[str] = "san_pham"
    PCT_CTV: Final[str] = "pct_ctv"
    PCT_KHACH: Final[str] = "pct_khach"
    IS_ACTIVE: Final[str] = "is_active"
    PACKAGE: Final[str] = "package"
    PACKAGE_PRODUCT: Final[str] = "package_product"
    UPDATE: Final[str] = "update"
    PCT_PROMO: Final[str] = "pct_promo"

REFUND_TABLE: Final[str] = f"{SCHEMA}.refund"
class RefundColumns:
    ID: Final[str] = "id"
    MA_DON_HANG: Final[str] = "ma_don_hang"
    NGAY_THANH_TOAN: Final[str] = "ngay_thanh_toan"
    SO_TIEN: Final[str] = "so_tien"

SUPPLY_TABLE: Final[str] = f"{SCHEMA}.supply"
class SupplyColumns:
    SOURCE_NAME: Final[str] = "source_name"
    ID: Final[str] = "id"
    NUMBER_BANK: Final[str] = "number_bank"
    BIN_BANK: Final[str] = "bin_bank"
    ACTIVE_SUPPLY: Final[str] = "active_supply"

SUPPLY_PRICE_TABLE: Final[str] = f"{SCHEMA}.supply_price"
class SupplyPriceColumns:
    ID: Final[str] = "id"
    PRODUCT_ID: Final[str] = "product_id"
    SOURCE_ID: Final[str] = "source_id"
    PRICE: Final[str] = "price"

COLUMNS: Final[Mapping[str, Mapping[str, str]]] = {
    "account_storage": {
        "ID": AccountStorageColumns.ID,
        "USERNAME": AccountStorageColumns.USERNAME,
        "PASSWORD": AccountStorageColumns.PASSWORD,
        "MAIL_2ND": AccountStorageColumns.MAIL_2ND,
        "NOTE": AccountStorageColumns.NOTE,
        "STORAGE": AccountStorageColumns.STORAGE,
        "MAIL_FAMILY": AccountStorageColumns.MAIL_FAMILY,
    },
    "bank_list": {
        "BIN": BankListColumns.BIN,
        "BANK_NAME": BankListColumns.BANK_NAME,
    },
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
        "CAN_HOAN": OrderCanceledColumns.CAN_HOAN,
        "TINH_TRANG": OrderCanceledColumns.TINH_TRANG,
        "CHECK_FLAG": OrderCanceledColumns.CHECK_FLAG,
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
    "package_product": {
        "ID": PackageProductColumns.ID,
        "PACKAGE": PackageProductColumns.PACKAGE,
        "USERNAME": PackageProductColumns.USERNAME,
        "PASSWORD": PackageProductColumns.PASSWORD,
        "MAIL_2ND": PackageProductColumns.MAIL_2ND,
        "NOTE": PackageProductColumns.NOTE,
        "EXPIRED": PackageProductColumns.EXPIRED,
        "SUPPLIER": PackageProductColumns.SUPPLIER,
        "IMPORT": PackageProductColumns.IMPORT,
        "SLOT": PackageProductColumns.SLOT,
    },
    "payment_receipt": {
        "ID": PaymentReceiptColumns.ID,
        "MA_DON_HANG": PaymentReceiptColumns.MA_DON_HANG,
        "NGAY_THANH_TOAN": PaymentReceiptColumns.NGAY_THANH_TOAN,
        "SO_TIEN": PaymentReceiptColumns.SO_TIEN,
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
    "product_price": {
        "ID": ProductPriceColumns.ID,
        "SAN_PHAM": ProductPriceColumns.SAN_PHAM,
        "PCT_CTV": ProductPriceColumns.PCT_CTV,
        "PCT_KHACH": ProductPriceColumns.PCT_KHACH,
        "IS_ACTIVE": ProductPriceColumns.IS_ACTIVE,
        "PACKAGE": ProductPriceColumns.PACKAGE,
        "PACKAGE_PRODUCT": ProductPriceColumns.PACKAGE_PRODUCT,
        "UPDATE": ProductPriceColumns.UPDATE,
        "PCT_PROMO": ProductPriceColumns.PCT_PROMO,
    },
    "refund": {
        "ID": RefundColumns.ID,
        "MA_DON_HANG": RefundColumns.MA_DON_HANG,
        "NGAY_THANH_TOAN": RefundColumns.NGAY_THANH_TOAN,
        "SO_TIEN": RefundColumns.SO_TIEN,
    },
    "supply": {
        "SOURCE_NAME": SupplyColumns.SOURCE_NAME,
        "ID": SupplyColumns.ID,
        "NUMBER_BANK": SupplyColumns.NUMBER_BANK,
        "BIN_BANK": SupplyColumns.BIN_BANK,
        "ACTIVE_SUPPLY": SupplyColumns.ACTIVE_SUPPLY,
    },
    "supply_price": {
        "ID": SupplyPriceColumns.ID,
        "PRODUCT_ID": SupplyPriceColumns.PRODUCT_ID,
        "SOURCE_ID": SupplyPriceColumns.SOURCE_ID,
        "PRICE": SupplyPriceColumns.PRICE,
    },
}
