from decimal import Decimal

from .utils import _round_thousand


def _to_decimal(value, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def calculate_sale_price(
    order_code: str,
    base_price,
    pct_ctv=None,
    pct_khach=None,
    pct_promo=None,
    gia_nhap=None,
) -> int:
    """
    Tính giá bán theo mã đơn và các hệ số:
    - MAVC: base_price * pct_ctv
    - MAVL: MAVC * pct_khach
    - MAVK: MAVL * (1 - pct_promo)
    - MAVT: giá bán = 0
    - MAVN: giá bán = giá nhập (gia_nhap)
    - Khác: dùng base_price
    """
    ma = (order_code or "").upper()

    price_value = _to_decimal(base_price, "0")
    cost_value = _to_decimal(gia_nhap, "0") if gia_nhap is not None else price_value

    pct_ctv_val = _to_decimal(pct_ctv, "1") if pct_ctv is not None else Decimal("1")
    pct_khach_val = _to_decimal(pct_khach, "1") if pct_khach is not None else Decimal("1")
    pct_promo_val = _to_decimal(pct_promo, "0") if pct_promo is not None else Decimal("0")

    if ma.startswith("MAVT"):
        gia_ban = Decimal(0)
    elif ma.startswith("MAVN"):
        gia_ban = cost_value
    elif ma.startswith("MAVC"):
        gia_ban = price_value * pct_ctv_val
    elif ma.startswith("MAVL"):
        gia_ban = price_value * pct_ctv_val * pct_khach_val
    elif ma.startswith("MAVK"):
        gia_ban = (price_value * pct_ctv_val * pct_khach_val) * (Decimal("1") - pct_promo_val)
    else:
        gia_ban = price_value

    return _round_thousand(gia_ban)


__all__ = ["calculate_sale_price"]
