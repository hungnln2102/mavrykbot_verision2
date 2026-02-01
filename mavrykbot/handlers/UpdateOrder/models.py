"""Data models and field configuration for update order."""
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence

from mavrykbot.core.db_schema import OrderListColumns
from mavrykbot.handlers.UpdateOrder.states import (
    EDIT_INPUT_LINK_KHACH,
    EDIT_INPUT_NGUON,
    EDIT_INPUT_SIMPLE,
    EDIT_INPUT_SO_NGAY,
    EDIT_INPUT_TEN_KHACH,
)


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
