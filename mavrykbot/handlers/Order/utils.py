import logging
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from telegram.error import BadRequest

from mavrykbot.core.utils import escape_mdv2, round_thousand, parse_price

logger = logging.getLogger(__name__)


# Re-export for backward compatibility
_round_thousand = round_thousand
_parse_price = parse_price


def extract_days_from_ma_sp(ma_sp: str) -> int:
    match = re.search(r"--(\d+)m", ma_sp.lower())
    if match:
        thang = int(match.group(1))
        return 365 if thang == 12 else thang * 30
    return 0


def tinh_ngay_het_han(ngay_bat_dau_str: str, so_ngay_dang_ky: str | int):
    try:
        ngay_bat_dau = datetime.strptime(ngay_bat_dau_str, "%d/%m/%Y").date()
        tong_ngay = int(so_ngay_dang_ky)
        so_nam = tong_ngay // 365
        so_ngay_con_lai = tong_ngay % 365
        so_thang = so_ngay_con_lai // 30
        so_ngay_du = so_ngay_con_lai % 30
        ngay_het_han = ngay_bat_dau + relativedelta(
            years=so_nam,
            months=so_thang,
            days=so_ngay_du - 1
        )
        return ngay_het_han
    except (ValueError, TypeError) as e:
        logger.error(f"[LỖI TÍNH NGÀY]: {e}")
        return None


def md(text: str) -> str:
    if text is None: return ""
    return escape_mdv2(str(text).replace("...", "…"))


async def safe_edit_md(bot, chat_id: int, message_id: int, text: str, reply_markup=None, try_plain: bool = True):
    try:
        return await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, reply_markup=reply_markup, parse_mode="MarkdownV2"
        )
    except BadRequest:
        if try_plain:
            return await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=text, reply_markup=reply_markup
            )
        raise


async def safe_send_md(bot, chat_id: int, text: str, reply_markup=None, try_plain: bool = True):
    try:
        return await bot.send_message(
            chat_id=chat_id, text=text,
            reply_markup=reply_markup, parse_mode="MarkdownV2"
        )
    except BadRequest:
        if try_plain:
            return await bot.send_message(
                chat_id=chat_id, text=text, reply_markup=reply_markup
            )
        raise
