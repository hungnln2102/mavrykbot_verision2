"""General helper utilities for the SQL-based bot backend."""
from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timedelta, timezone

logger_name = __name__

VN_TZ = timezone(timedelta(hours=7))


def escape_mdv2(text: str) -> str:
    """Escape MarkdownV2 meta characters."""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.!])", r"\\\1", text)


def compute_dates(so_ngay: int, start_date: datetime | None = None):
    tz_today = datetime.now(VN_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start = start_date or tz_today
    end = start + timedelta(days=int(so_ngay))
    con_lai = (end - tz_today).days
    fmt = lambda d: d.strftime("%d/%m/%Y")
    return fmt(start), fmt(end), max(con_lai, 0)


def to_int(value, default=0):
    if value is None:
        return default
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else default


def format_date_dmy(date_obj: datetime):
    return date_obj.strftime("%d/%m/%Y")


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

