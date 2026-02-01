"""General helper utilities for the SQL-based bot backend."""
from __future__ import annotations

import re
import secrets
import string
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

logger_name = __name__

DATE_FMT = "%d/%m/%Y"


def escape_mdv2(text: str) -> str:
    """Escape MarkdownV2 meta characters."""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.!])", r"\\\1", text)


def to_int(value, default=0):
    if value is None:
        return default
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else default


def normalize_product_duration(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    s = re.sub(r"[\u2010-\u2015]", "-", text)
    return re.sub(r"-+\s*(\d+)\s*m\b", r"--\1m", s, flags=re.I)


def chuan_hoa_gia(text: str):
    try:
        s = str(text).lower().strip()
        is_thousand_k = "k" in s
        has_separator = "." in s
        digits = "".join(filter(str.isdigit, s))
        if not digits:
            return "0", 0
        number = int(digits)
        if is_thousand_k:
            number *= 1000
        elif not is_thousand_k and not has_separator and number < 5000:
            number *= 1000
        return "{:,}".format(number), number
    except (ValueError, TypeError):
        return "0", 0

def generate_unique_id(prefix: str | None = None) -> str:
    """Generates a unique, 11-character alphanumeric ID with a given prefix."""
    prefix_map = {
        'le': 'MAVL',
        'ctv': 'MAVC',
        'mavk': 'MAVK'
    }
    final_prefix = prefix_map.get(prefix.lower(), 'MAV') if prefix else 'MAV'
    
    # Ensure the prefix is 4 characters
    final_prefix = final_prefix.ljust(4, 'X')

    # Generate 7 random characters
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(7))
    
    return f"{final_prefix}{random_part}"


# =============================================================================
# Consolidated utility functions (moved from handlers)
# =============================================================================

def round_thousand(value) -> int:
    """Round to nearest thousand: >=500 goes up, <500 goes down (non-positive -> 0)."""
    try:
        number = int(Decimal(value))
    except Exception:
        return 0
    if number <= 0:
        return 0
    remainder = number % 1000
    base = number - remainder
    return base + 1000 if remainder >= 500 else base


def parse_date(value) -> Optional[date]:
    """Parse date from various formats (YYYY-MM-DD, DD/MM/YYYY) or date/datetime objects."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value_str = str(value).strip()
    if not value_str:
        return None
    for fmt in ("%Y-%m-%d", DATE_FMT):
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue
    return None


def coerce_int(value) -> Optional[int]:
    """Coerce value to int, handling Decimal, string with commas, etc."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        return int(value)
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def parse_price(s: str) -> int:
    """Parse price string (e.g., '150k', '150.000', '150000') to int. Returns -1 on error."""
    try:
        s = str(s).strip().replace("đ", "").replace("₫", "").replace(" ", "")
        if not s:
            return -1
        s = s.replace(",", ".")
        if "." not in s:
            value = int(s) * 1000
            return round_thousand(value)
        parts = s.split('.')
        integer_part = "".join(parts[:-1])
        decimal_part = parts[-1]
        if not integer_part:
            integer_part = "0"
        reformatted_string = f"{integer_part}.{decimal_part}"
        base_value = float(reformatted_string)
        value = int(base_value * 1000)
        return round_thousand(value)
    except (ValueError, IndexError):
        return -1


def format_date_vn(value: Optional[date]) -> str:
    """Format date as DD/MM/YYYY Vietnamese format."""
    return value.strftime(DATE_FMT) if value else ""


def format_currency_vn(value: Optional[int]) -> str:
    """Format currency with Vietnamese style (dots as thousand separator)."""
    amount = int(value or 0)
    return "{:,}".format(amount).replace(",", ".")


def md(text: str) -> str:
    """Shorthand for escape_mdv2 with ellipsis normalization."""
    if text is None:
        return ""
    return escape_mdv2(str(text).replace("...", "…"))

