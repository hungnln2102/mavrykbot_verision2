import logging
import re
import asyncio
import requests
import string
from datetime import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from telegram.error import BadRequest

# --- Imports cho PostgreSQL và tiện ích ---
from mavrykbot.core.utils import generate_unique_id, escape_mdv2
from mavrykbot.handlers.menu import show_main_selector
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    ORDER_LIST_TABLE, OrderListColumns, 
    PRODUCT_PRICE_TABLE, ProductPriceColumns,
    SUPPLY_TABLE, SupplyColumns, 
    SUPPLY_PRICE_TABLE, SupplyPriceColumns
)
# ------------------------------------------

logger = logging.getLogger(__name__)

# =============================
# Trạng thái Conversation
# =============================
(
    STATE_CHON_LOAI_KHACH, STATE_NHAP_TEN_SP, STATE_CHON_PACKAGE, STATE_CHON_PACKAGE_PRODUCT, 
    STATE_CHON_MA_SP, STATE_NHAP_MA_MOI,
    STATE_CHON_NGUON, STATE_NHAP_NGUON_MOI, STATE_NHAP_GIA_NHAP, STATE_NHAP_THONG_TIN,
    STATE_NHAP_TEN_KHACH, STATE_NHAP_LINK_KHACH, STATE_NHAP_SLOT,
    STATE_NHAP_GIA_BAN, STATE_NHAP_NOTE
) = range(15)

# =============================
# Tiện ích chung + MarkdownV2-safe
# =============================

def _round_thousand(value: int) -> int:
    if value <= 0:
        return 0
    return ((value + 999) // 1000) * 1000


def _parse_price(s: str) -> int:
    try:
        s = str(s).strip().replace("đ", "").replace("₫", "").replace(" ", "")
        if not s: return -1
        s = s.replace(",", ".")
        if "." not in s:
            value = int(s) * 1000
            return _round_thousand(value)
        parts = s.split('.')
        integer_part = "".join(parts[:-1])
        decimal_part = parts[-1]
        if not integer_part: integer_part = "0"
        reformatted_string = f"{integer_part}.{decimal_part}"
        base_value = float(reformatted_string)
        value = int(base_value * 1000)
        return _round_thousand(value)
    except (ValueError, IndexError):
        return -1

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

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['main_message_id'] = query.message.message_id

    keyboard = [
        [
            InlineKeyboardButton("Khách Lẻ", callback_data="le"),
            InlineKeyboardButton("Cộng Tác Viên", callback_data="ctv"),
        ],
        [
            InlineKeyboardButton("Khuyến Mãi", callback_data="mavk"),
        ],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")],
    ]

    chat_id = query.message.chat.id
    await safe_edit_md(
        context.bot, chat_id, query.message.message_id,
        text="📦 *Khởi Tạo Đơn Hàng Mới*\n\nVui lòng lựa chọn phân loại khách hàng:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_LOAI_KHACH


async def chon_loai_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["loai_khach"] = query.data
    chat_id = query.message.chat.id

    try:
        ma_don = generate_unique_id(query.data) 
        context.user_data["ma_don"] = ma_don
    except Exception as e:
        logger.error(f"Lỗi tạo mã đơn: {e}")
        await safe_edit_md(context.bot, chat_id, query.message.message_id, md("❌ Lỗi tạo mã đơn."))
        return await end_add(update, context, success=False)

    text = f"🧾 Mã đơn: `{md(ma_don)}`\n\n🏷️ Vui lòng nhập *Tên Sản Phẩm*:"
    await safe_edit_md(
        context.bot, chat_id, query.message.message_id,
        text=text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_TEN_SP


# =============================
# 2) Nhập tên sản phẩm — ĐÃ CHUYỂN SANG SQL
# =============================
async def nhap_ten_sp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ten_sp = update.message.text.strip()
    await update.message.delete()
    context.user_data['ten_san_pham_raw'] = ten_sp
    main_message_id = context.user_data.get('main_message_id')
    chat_id = update.effective_chat.id

    await safe_edit_md(
        context.bot, chat_id, main_message_id,
        text=f"🔎 Đang tìm sản phẩm *{md(ten_sp)}* trong SQL…"
    )

    try:
        sql_query = f"""
            SELECT 
                {ProductPriceColumns.ID}, {ProductPriceColumns.SAN_PHAM}, 
                {ProductPriceColumns.PACKAGE}, {ProductPriceColumns.PACKAGE_PRODUCT}
            FROM {PRODUCT_PRICE_TABLE}
            WHERE 
                {ProductPriceColumns.SAN_PHAM} ILIKE %s 
                AND LOWER(CAST({ProductPriceColumns.IS_ACTIVE} AS TEXT)) = 'true'
            ORDER BY {ProductPriceColumns.PACKAGE}, {ProductPriceColumns.PACKAGE_PRODUCT}
        """
        search_term = f'%{ten_sp}%'
        matched_products = db.fetch_all(sql_query, (search_term,))
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn PRODUCT_PRICE: {e}")
        await safe_edit_md(context.bot, chat_id, main_message_id, md("❌ Lỗi kết nối CSDL."))
        return await end_add(update, context, success=False)

    if not matched_products:
        await safe_edit_md(
            context.bot, chat_id, main_message_id,
            text=md("⚠️ Không có mã sản phẩm hoạt động nào được tìm thấy."),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        # Chuyển thẳng sang nhập mã mới vì không tìm thấy gì
        return STATE_NHAP_MA_MOI

    context.user_data["matched_products"] = matched_products
    packages = sorted(list(set(row[2] for row in matched_products if row[2])))

    if not packages:
        # Nếu không có package, chuyển thẳng sang chọn mã sản phẩm (san_pham) nếu có
        product_map = {row[1]: row[0] for row in matched_products}
        context.user_data["product_map"] = product_map
        return await _display_final_products(chat_id, main_message_id, context, list(product_map.keys()))

    # If there's only one package, auto-select it and proceed to package_product selection
    if len(packages) == 1:
        selected_package = packages[0]
        context.user_data['selected_package'] = selected_package
        return await _display_package_products(chat_id, main_message_id, context, selected_package)

    keyboard, row = [], []
    for pkg in packages:
        row.append(InlineKeyboardButton(text=pkg, callback_data=f"chon_pkg|{pkg}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")])

    await safe_edit_md(
        context.bot, chat_id, main_message_id,
        text=f"📂 Vui lòng chọn *Gói sản phẩm* cho *{md(ten_sp)}*:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_PACKAGE


async def _display_package_products(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, selected_package: str) -> int:
    """Helper to display package product selection."""
    matched_products = context.user_data.get("matched_products", [])
    
    package_products = sorted(list(set(
        row[3] for row in matched_products if row[2] == selected_package and row[3]
    )))

    if not package_products:
        # Nếu không có package_product, chuyển thẳng sang chọn mã sản phẩm (san_pham)
        final_products = [row for row in matched_products if row[2] == selected_package]
        product_map = {row[1]: row[0] for row in final_products}
        context.user_data["product_map"] = product_map
        return await _display_final_products(chat_id, message_id, context, list(product_map.keys()))

    keyboard, row = [], []
    for pkg_prod in package_products:
        row.append(InlineKeyboardButton(text=pkg_prod, callback_data=f"chon_pkg_prod|{pkg_prod}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")])

    await safe_edit_md(
        context.bot, chat_id, message_id,
        text=f"📦 Gói: *{md(selected_package)}*\n\n🏷️ Vui lòng chọn *Loại sản phẩm*:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_PACKAGE_PRODUCT

async def _display_final_products(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, product_keys: list[str]) -> int:
    """Helper to display final product selection."""
    num_columns = 3 if len(product_keys) > 9 else 2
    keyboard, row = [], []
    for ma_sp in product_keys:
        row.append(InlineKeyboardButton(text=ma_sp, callback_data=f"chon_ma|{ma_sp}"))
        if len(row) == num_columns:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("✏️ Nhập Mã Mới", callback_data="nhap_ma_moi"),
        InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")
    ])

    await safe_edit_md(
        context.bot, chat_id, message_id,
        text=f"📦 Vui lòng chọn *Mã sản phẩm* phù hợp:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_MA_SP


async def chon_package_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_package = query.data.split("|", 1)[1]
    context.user_data['selected_package'] = selected_package
    
    main_message_id = context.user_data.get('main_message_id')
    return await _display_package_products(query.message.chat.id, main_message_id, context, selected_package)


async def chon_package_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_pkg_prod = query.data.split("|", 1)[1]
    context.user_data['selected_pkg_prod'] = selected_pkg_prod

    matched_products = context.user_data.get("matched_products", [])
    selected_package = context.user_data.get("selected_package")

    # Filter by both package and package_product to get final product list
    final_products = [
        row for row in matched_products 
        if row[2] == selected_package and row[3] == selected_pkg_prod
    ]

    if not final_products:
        await safe_edit_md(
            context.bot, query.message.chat.id, query.message.message_id,
            text=md("⚠️ Không có mã sản phẩm hoạt động nào được tìm thấy."),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return await end_add(update, context, success=False)

    # product_map: {san_pham_name: product_id}
    product_map = {row[1]: row[0] for row in final_products}
    context.user_data["product_map"] = product_map
    
    product_keys = list(product_map.keys())

    return await _display_final_products(query.message.chat.id, query.message.message_id, context, product_keys)


async def nhap_ma_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    await safe_edit_md(
        context.bot, chat_id, query.message.message_id,
        text="✏️ Vui lòng nhập *Mã Sản Phẩm mới* \\(ví dụ: `Netflix--1m`\\)\\:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_MA_MOI


# Nếu không có mã hợp lệ trong CSDL, sau khi nhập mã mới -> đi thẳng sang nhập Nguồn mới
async def xu_ly_ma_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ma_moi = update.message.text.strip().replace("—", "--").replace("–", "--")
    await update.message.delete()
    context.user_data['ma_chon'] = ma_moi
    so_ngay = extract_days_from_ma_sp(ma_moi)
    if so_ngay > 0:
        context.user_data['so_ngay'] = str(so_ngay)

    chat_id = update.effective_chat.id
    
    # Chuyển thẳng sang nhập Tên Nguồn mới (vì không tra cứu/chọn nguồn)
    await safe_edit_md(
        context.bot, chat_id, context.user_data['main_message_id'],
        text="🚚 Vui lòng nhập *tên Nguồn hàng*\\:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_NGUON_MOI


# =============================
# 3) Chọn mã -> liệt kê nguồn từ Supply_Price (ĐÃ CHUYỂN SANG SQL)
# =============================
async def chon_ma_sp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ma_chon = query.data.split("|", 1)[1]
    context.user_data['ma_chon'] = ma_chon

    product_map = context.user_data.get("product_map", {})
    product_id = product_map.get(ma_chon)

    if not product_id:
        await safe_edit_md(context.bot, query.message.chat.id, query.message.message_id, md("❌ Lỗi: Không tìm thấy ID sản phẩm."))
        return await end_add(update, context, success=False)

    context.user_data['product_id'] = product_id

    so_ngay = extract_days_from_ma_sp(ma_chon)
    if so_ngay > 0:
        context.user_data['so_ngay'] = str(so_ngay)

    try:
        # Truy vấn SQL JOIN 3 bảng để tìm nguồn hàng (SupplyName) và giá (Price)
        sql_query = f"""
            SELECT 
                T1.{SupplyColumns.SOURCE_NAME}, T2.{SupplyPriceColumns.PRICE}
            FROM {SUPPLY_TABLE} AS T1
            JOIN {SUPPLY_PRICE_TABLE} AS T2
                ON T1.{SupplyColumns.ID} = T2.{SupplyPriceColumns.SOURCE_ID}
            WHERE T2.{SupplyPriceColumns.PRODUCT_ID} = %s AND T2.{SupplyPriceColumns.PRICE} > 0
            ORDER BY T1.{SupplyColumns.SOURCE_NAME}
        """
        source_prices = db.fetch_all(sql_query, (product_id,)) 
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn Supply Price: {e}")
        await safe_edit_md(context.bot, query.message.chat.id, query.message.message_id, md("❌ Lỗi kết nối CSDL khi tìm nguồn hàng."))
        return await end_add(update, context, success=False)

    # 2. Xây dựng Keyboard và Map giá
    keyboard, row = [], []
    source_price_map = {} 
    
    for src_name, price in source_prices:
        price_display = f'{price:,} đ'.replace(',', '.') 
        label = f"{src_name} - {price_display}"
        row.append(InlineKeyboardButton(label, callback_data=f"chon_nguon|{src_name}"))
        source_price_map[src_name] = price 
        if len(row) == 2:
            keyboard.append(row); row = []
    if row:
        keyboard.append(row)
        
    context.user_data['source_price_map'] = source_price_map

    keyboard.append([InlineKeyboardButton("➕ Nguồn Mới", callback_data="nguon_moi"), InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")])
    await safe_edit_md(
        context.bot, query.message.chat.id, query.message.message_id,
        text=f"📦 Mã SP: `{md(ma_chon)}`\n\n🚚 Vui lòng chọn *Nguồn hàng*:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_CHON_NGUON


# =============================
# 4) Chọn nguồn -> lấy Giá nhập, Giá bán (ĐÃ CHUYỂN SANG SQL)
# =============================
async def chon_nguon_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 1)
    if len(parts) < 2:
        logger.warning(f"Received unexpected callback_data format in chon_nguon_handler: {query.data}")
        await safe_edit_md(context.bot, query.message.chat.id, query.message.message_id, "❌ Đã xảy ra lỗi, vui lòng thử lại từ đầu.")
        return await end_add(update, context, success=False)

    nguon = parts[1].strip()
    context.user_data["nguon"] = nguon

    product_id = context.user_data.get('product_id')
    source_price_map = context.user_data.get('source_price_map', {})
    ma_don = context.user_data.get("ma_don", "")

    # 1. Lấy Giá nhập 
    gia_nhap = source_price_map.get(nguon, 0)
    context.user_data["gia_nhap_value"] = gia_nhap
    logger.info(f"LOG_PRICE_CALC | Initial input price (gia_nhap) for source '{nguon}': {gia_nhap}")
    
    # Mặc định giá bán bằng giá nhập, sử dụng Decimal
    gia_ban = Decimal(gia_nhap)

    try:
        # 2. Lấy giá cao nhất từ nhà cung cấp cho sản phẩm này
        highest_price_query = f"""
            SELECT MAX({SupplyPriceColumns.PRICE}) 
            FROM {SUPPLY_PRICE_TABLE} 
            WHERE {SupplyPriceColumns.PRODUCT_ID} = %s
        """
        highest_price_result = db.fetch_one(highest_price_query, (product_id,))
        highest_price = highest_price_result[0] if highest_price_result and highest_price_result[0] is not None else Decimal(0)
        logger.info(f"LOG_PRICE_CALC | Highest Price for product_id {product_id}: {highest_price}")


        if highest_price > 0:
            # 3. Lấy các hệ số nhân giá từ bảng Product_Price
            percentages_query = f"""
                SELECT {ProductPriceColumns.PCT_CTV}, {ProductPriceColumns.PCT_KHACH} 
                FROM {PRODUCT_PRICE_TABLE} 
                WHERE {ProductPriceColumns.ID} = %s
            """
            percentages_result = db.fetch_one(percentages_query, (product_id,))
            
            if percentages_result:
                pct_ctv, pct_khach = percentages_result
                pct_ctv = Decimal(str(pct_ctv)) if pct_ctv is not None else Decimal('1.0')
                pct_khach = Decimal(str(pct_khach)) if pct_khach is not None else Decimal('1.0')
                logger.info(f"LOG_PRICE_CALC | Percentages found - PCT_CTV: {pct_ctv}, PCT_KHACH: {pct_khach}")


                # 4. Tính giá bán dựa trên mã đơn hàng
                if ma_don.startswith("MAVC"):
                    gia_ban = highest_price * pct_ctv
                    logger.info(f"LOG_PRICE_CALC | MAVC branch: final_price = highest_price * pct_ctv = {highest_price} * {pct_ctv} = {gia_ban}")
                elif ma_don.startswith("MAVL"):
                    gia_ctv = highest_price * pct_ctv
                    gia_ban = gia_ctv * pct_khach
                    logger.info(f"LOG_PRICE_CALC | MAVL branch: ctv_price = highest_price * pct_ctv = {highest_price} * {pct_ctv} = {gia_ctv}")
                    logger.info(f"LOG_PRICE_CALC | MAVL branch: final_price = ctv_price * pct_khach = {gia_ctv} * {pct_khach} = {gia_ban}")

        # Trường hợp MAVK, giá bán bằng giá nhập đã được set ở trên
        if ma_don.startswith("MAVK"):
            gia_ban = Decimal(gia_nhap)
            logger.info(f"LOG_PRICE_CALC | MAVK branch: final_price = input_price = {gia_ban}")


    except Exception as e:
        logger.error(f"Lỗi khi tính giá bán theo logic mới: {e}")
        # Trong trường hợp lỗi, giá bán sẽ là giá nhập
        gia_ban = Decimal(gia_nhap)
        logger.info(f"LOG_PRICE_CALC | Exception fallback: final_price = input_price = {gia_ban}")

    gia_ban_int = int(gia_ban)
    gia_ban_rounded = _round_thousand(gia_ban_int)
    logger.info(
        "LOG_PRICE_CALC | Price before rounding: %s, After rounding to nearest thousand: %s",
        gia_ban_int,
        gia_ban_rounded,
    )

    context.user_data["gia_ban_value"] = gia_ban_rounded
    logger.info(f"LOG_PRICE_CALC | Final calculated price (integer): {gia_ban_rounded}")

    await safe_edit_md(
        context.bot, query.message.chat.id, query.message.message_id, 
        text="📝 Vui lòng nhập *Thông tin đơn hàng*:", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_THONG_TIN


# =============================
# Các bước nhập dữ liệu trung gian (Giữ nguyên)
# =============================
async def chon_nguon_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await safe_edit_md(
        context.bot, query.message.chat.id, query.message.message_id,
        text="🚚 Vui lòng nhập *tên Nguồn hàng mới*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_NGUON_MOI


async def nhap_nguon_moi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nguon"] = update.message.text.strip()
    await update.message.delete()
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="💰 Vui lòng nhập *Giá nhập*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_GIA_NHAP


async def nhap_gia_nhap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gia_nhap_raw = update.message.text.strip()
    await update.message.delete()
    
    gia_nhap_value = _parse_price(gia_nhap_raw)

    if gia_nhap_value < 0:
        await safe_edit_md(
            context.bot, update.effective_chat.id, context.user_data['main_message_id'],
            text="⚠️ Giá nhập không hợp lệ. Vui lòng chỉ nhập số:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return STATE_NHAP_GIA_NHAP

    context.user_data["gia_nhap_value"] = gia_nhap_value

    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="📝 Vui lòng nhập *Thông tin đơn hàng*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_THONG_TIN

async def nhap_thong_tin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["thong_tin_don"] = update.message.text.strip()
    await update.message.delete()
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="👤 Vui lòng nhập *tên khách hàng*:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
    )
    return STATE_NHAP_TEN_KHACH


async def nhap_ten_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["khach_hang"] = update.message.text.strip()
    await update.message.delete()
    keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_link")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="🔗 Vui lòng nhập *thông tin liên hệ* hoặc bấm Bỏ Qua:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_LINK_KHACH


async def nhap_link_khach_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, skip: bool = False) -> int:
    query = update.callback_query
    if skip:
        context.user_data["link_khach"] = ""
        await query.answer()
        chat_id = query.message.chat.id
        mid = query.message.message_id
    else:
        context.user_data["link_khach"] = update.message.text.strip()
        await update.message.delete()
        chat_id = update.effective_chat.id
        mid = context.user_data['main_message_id']
    keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_slot")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
    await safe_edit_md(
        context.bot, chat_id, mid,
        text="🧩 Vui lòng nhập *Slot* \\(nếu có\\) hoặc bấm Bỏ Qua:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_SLOT


async def nhap_slot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, skip: bool = False) -> int:
    query = update.callback_query
    if skip:
        context.user_data["slot"] = ""
        await query.answer()
        chat_id = query.message.chat.id
        mid = query.message.message_id
    else:
        context.user_data["slot"] = update.message.text.strip()
        await update.message.delete()
        chat_id = update.effective_chat.id
        mid = context.user_data['main_message_id']

    if "gia_ban_value" in context.user_data and context.user_data["gia_ban_value"] > 0:
        keyboard = [[InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_note")], [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]]
        await safe_edit_md(
            context.bot, chat_id, mid,
            text="📝 Vui lòng nhập *Ghi chú* \\(nếu có\\) hoặc bấm Bỏ Qua:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STATE_NHAP_NOTE
    else:
        await safe_edit_md(
            context.bot, chat_id, mid,
            text="💵 Vui lòng nhập *Giá bán*:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return STATE_NHAP_GIA_BAN


async def nhap_gia_ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    gia_ban_raw = update.message.text.strip()
    await update.message.delete()
    
    gia_ban_value = _parse_price(gia_ban_raw)

    if gia_ban_value < 0:
        await safe_edit_md(
            context.bot, update.effective_chat.id, context.user_data['main_message_id'],
            text="⚠️ Giá bán không hợp lệ. Vui lòng chỉ nhập số:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]])
        )
        return STATE_NHAP_GIA_BAN

    gia_ban_rounded = _round_thousand(gia_ban_value)
    logger.info(f"LOG_PRICE_CALC | Manual price entered: {gia_ban_value}, Rounded to nearest thousand: {gia_ban_rounded}")

    context.user_data["gia_ban_value"] = gia_ban_rounded

    keyboard = [
        [InlineKeyboardButton("⏭️ Bỏ Qua", callback_data="skip_note")],
        [InlineKeyboardButton("❌ Hủy", callback_data="cancel_add")]
    ]
    await safe_edit_md(
        context.bot, update.effective_chat.id, context.user_data['main_message_id'],
        text="📝 Vui lòng nhập *Ghi chú* \\(nếu có\\) hoặc bấm Bỏ Qua:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_NHAP_NOTE

async def nhap_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, skip: bool = False) -> int:
    query = update.callback_query
    if skip:
        context.user_data["note"] = ""
        await query.answer()
    else:
        context.user_data["note"] = update.message.text.strip()
        await update.message.delete()
    return await hoan_tat_don(update, context)


async def hoan_tat_don(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    chat_id = query.message.chat.id if query else update.effective_chat.id
    main_message_id = context.user_data.get('main_message_id')

    if main_message_id:
        await safe_edit_md(
            context.bot, chat_id, main_message_id,
            text="⏳ Đang hoàn tất đơn hàng, vui lòng chờ…"
        )

    try:
        info = context.user_data
        
        # --- Chuẩn bị dữ liệu cho SQL ---
        ngay_bat_dau_dt = datetime.now().date()
        ngay_bat_dau_str = ngay_bat_dau_dt.strftime("%d/%m/%Y")
        
        so_ngay = int(info.get("so_ngay", "0"))
        gia_ban_value = info.get("gia_ban_value", 0)
        
        ngay_het_han_dt = tinh_ngay_het_han(ngay_bat_dau_str, so_ngay)
        
        # Ghi vào PostgreSQL
        try:
            sql_query = f"""
                INSERT INTO {ORDER_LIST_TABLE} (
                    {OrderListColumns.ID_DON_HANG}, {OrderListColumns.SAN_PHAM}, 
                    {OrderListColumns.THONG_TIN_SAN_PHAM}, {OrderListColumns.KHACH_HANG},
                    {OrderListColumns.LINK_LIEN_HE}, {OrderListColumns.SLOT}, 
                    {OrderListColumns.NGAY_DANG_KI}, {OrderListColumns.SO_NGAY_DA_DANG_KI},
                    {OrderListColumns.HET_HAN}, {OrderListColumns.NGUON}, 
                    {OrderListColumns.GIA_NHAP}, {OrderListColumns.GIA_BAN}, 
                    {OrderListColumns.NOTE}, {OrderListColumns.TINH_TRANG},
                    {OrderListColumns.CHECK_FLAG}
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            params = (
                info.get("ma_don", ""),
                info.get("ma_chon", info.get("ten_san_pham_raw", "")),
                info.get("thong_tin_don", ""),
                info.get("khach_hang", ""),
                info.get("link_khach", ""),
                info.get("slot", ""),
                ngay_bat_dau_dt,            
                so_ngay,
                ngay_het_han_dt,            
                info.get("nguon", ""),
                info.get("gia_nhap_value", 0), 
                gia_ban_value,              
                info.get("note", ""),
                 "Chưa Thanh Toán",
                 None
             )
            
            db.execute(sql_query, params)

        except Exception as e:
            logger.error(f"Lỗi khi ghi đơn hàng vào PostgreSQL: {e}")
            await safe_edit_md(context.bot, chat_id, main_message_id, md(f"❌ Lỗi khi ghi đơn hàng vào PostgreSQL: {e}"))
            return await end_add(update, context, success=False)
        
        
        ma_don_final = info.get('ma_don','')
        caption = (
            f"✅ Đơn hàng `{escape_mdv2(ma_don_final)}` đã được tạo thành công\\!\n\n"
            f"📦 *THÔNG TIN SẢN PHẨM*\n"
            f"🔹 *Tên Sản Phẩm:* {escape_mdv2(info.get('ma_chon', ''))}\n"
            f"📝 *Thông Tin Đơn Hàng:* `{escape_mdv2(info.get('thong_tin_don', ''))}`\n"
            f"📆 *Ngày Bắt đầu:* {escape_mdv2(ngay_bat_dau_str)}\n"
            f"⏳ *Thời hạn:* {escape_mdv2(str(so_ngay))} ngày\n"
            f"📅 *Ngày Hết hạn:* {escape_mdv2(ngay_het_han_dt.strftime('%d/%m/%Y') if ngay_het_han_dt else 'N/A')}\n"
            f"💵 *Giá bán:* {escape_mdv2(f'{gia_ban_value:,} đ'.replace(',', '.'))}\n\n" 
            f" *━━━━━━ 👤 ━━━━━━*\n"
            f"👤 *THÔNG TIN KHÁCH HÀNG*\n"
            f"🔸 *Tên Khách Hàng:* {escape_mdv2(info.get('khach_hang', ''))}\n\n"
            f" *━━━━━━ 💳 ━━━━━━*\n"
            f"📢 *HƯỚNG DẪN THANH TOÁN*\n"
            f"📢 *STK:* 9183400998\n"
            f"📢 *Nội dung:* Thanh toán `{escape_mdv2(ma_don_final)}`"
        )

        qr_url = (
            "https://img.vietqr.io/image/VPB-9183400998-compact2.png"
            f"?amount={gia_ban_value}&addInfo={requests.utils.quote(ma_don_final)}"
            "&accountName=NGO LE NGOC HUNG"
        )

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=main_message_id)
        except Exception:
            pass
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=qr_url, caption=caption, parse_mode="MarkdownV2")
        except BadRequest:
            await context.bot.send_photo(chat_id=chat_id, photo=qr_url, caption=caption)

        await show_main_selector(update, context, edit=False)

    except Exception as e:
        logger.error(f"Lỗi không mong muốn trong hoan_tat_don: {e}")
        await safe_send_md(context.bot, chat_id, escape_mdv2(f"Đã có lỗi xảy ra khi hoàn tất đơn: {e}"))
    finally:
        return await end_add(update, context, success=True)

async def end_add(update: Update | None, context: ContextTypes.DEFAULT_TYPE, success: bool = True) -> int:
    if update:
        query = update.callback_query
        context.user_data.clear()
        if not success and query:
            await asyncio.sleep(1)
            await show_main_selector(update, context, edit=False)
    else:
        context.user_data.clear()
        
    return ConversationHandler.END


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await safe_edit_md(context.bot, query.message.chat.id, query.message.message_id, md("❌ Đã hủy thao tác thêm đơn."))
    return await end_add(update, context, success=False)


def get_add_order_conversation_handler():
    cancel_handler = CallbackQueryHandler(cancel_add, pattern="^cancel_add$")
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add, pattern="^add$")],
        states={
            STATE_CHON_LOAI_KHACH: [cancel_handler, CallbackQueryHandler(chon_loai_khach_handler, pattern=r"^(le|ctv|mavk)$")],
            STATE_NHAP_TEN_SP: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_ten_sp_handler)],
            STATE_CHON_PACKAGE: [cancel_handler, CallbackQueryHandler(chon_package_handler, pattern=r"^chon_pkg\|")],
            STATE_CHON_PACKAGE_PRODUCT: [cancel_handler, CallbackQueryHandler(chon_package_product_handler, pattern=r"^chon_pkg_prod\|")],
            STATE_CHON_MA_SP: [cancel_handler, CallbackQueryHandler(chon_ma_sp_handler, pattern=r"^chon_ma\|"), CallbackQueryHandler(nhap_ma_moi_handler, pattern="^nhap_ma_moi$")],
            STATE_CHON_NGUON: [cancel_handler, CallbackQueryHandler(chon_nguon_handler, pattern=r"^chon_nguon\|"), CallbackQueryHandler(chon_nguon_moi_handler, pattern="^nguon_moi$")],
            STATE_NHAP_MA_MOI: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, xu_ly_ma_moi_handler)],
            STATE_NHAP_NGUON_MOI: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_nguon_moi_handler)],
            STATE_NHAP_GIA_NHAP: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_gia_nhap_handler)],
            STATE_NHAP_THONG_TIN: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_thong_tin_handler)],
            STATE_NHAP_TEN_KHACH: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_ten_khach_handler)],
            STATE_NHAP_LINK_KHACH: [cancel_handler, CallbackQueryHandler(lambda u, c: nhap_link_khach_handler(u, c, skip=True), pattern="^skip_link$"), MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_link_khach_handler)],
            STATE_NHAP_SLOT: [cancel_handler, CallbackQueryHandler(lambda u, c: nhap_slot_handler(u, c, skip=True), pattern="^skip_slot$"), MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_slot_handler)],
            STATE_NHAP_GIA_BAN: [cancel_handler, MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_gia_ban_handler)],
            STATE_NHAP_NOTE: [cancel_handler, CallbackQueryHandler(lambda u, c: nhap_note_handler(u, c, skip=True), pattern="^skip_note$"), MessageHandler(filters.TEXT & ~filters.COMMAND, nhap_note_handler)],
        },
        fallbacks=[cancel_handler],
        name="add_order_conversation",
        persistent=False,
        allow_reentry=True,
    )
