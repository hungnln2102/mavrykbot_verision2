import logging
from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from mavrykbot.core.database import db
from mavrykbot.core.db_schema import (
    PRODUCT_TABLE,
    SUPPLY_PRICE_TABLE,
    SUPPLY_TABLE,
    VARIANT_TABLE,
    ProductColumns,
    SupplyColumns,
    SupplyPriceColumns,
    VariantColumns,
)

from .states import (
    STATE_NHAP_TEN_SP,
    STATE_CHON_PACKAGE,
    STATE_CHON_PACKAGE_PRODUCT,
    STATE_CHON_MA_SP,
    STATE_NHAP_MA_MOI,
    STATE_CHON_NGUON,
    STATE_NHAP_NGUON_MOI,
)
from .utils import safe_edit_md, md, extract_days_from_ma_sp
from .finalize import end_add

logger = logging.getLogger(__name__)


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
        search_term = f'%{ten_sp}%'
        matched_products = []

        sql_templates = [
            f"""
                SELECT 
                    v.{VariantColumns.ID},
                    v.{VariantColumns.DISPLAY_NAME},
                    p.{ProductColumns.PACKAGE_NAME},
                    v.{VariantColumns.VARIANT_NAME}
                FROM {VARIANT_TABLE} AS v
                JOIN {PRODUCT_TABLE} AS p
                    ON p.{ProductColumns.ID} = v.{VariantColumns.PRODUCT_ID}
                WHERE 
                    p.{ProductColumns.PACKAGE_NAME} ILIKE %s 
                    AND LOWER(CAST(v.{VariantColumns.IS_ACTIVE} AS TEXT)) = 'true'
                ORDER BY p.{ProductColumns.PACKAGE_NAME}, v.{VariantColumns.VARIANT_NAME}
            """,
            f"""
                SELECT 
                    v.{VariantColumns.ID},
                    v.{VariantColumns.DISPLAY_NAME},
                    p.{ProductColumns.PACKAGE_NAME},
                    v.{VariantColumns.VARIANT_NAME}
                FROM {VARIANT_TABLE} AS v
                JOIN {PRODUCT_TABLE} AS p
                    ON p.{ProductColumns.ID} = v.{VariantColumns.PRODUCT_ID}
                WHERE 
                    v.{VariantColumns.DISPLAY_NAME} ILIKE %s 
                    AND LOWER(CAST(v.{VariantColumns.IS_ACTIVE} AS TEXT)) = 'true'
                ORDER BY p.{ProductColumns.PACKAGE_NAME}, v.{VariantColumns.VARIANT_NAME}
            """,
            f"""
                SELECT 
                    v.{VariantColumns.ID},
                    v.{VariantColumns.DISPLAY_NAME},
                    p.{ProductColumns.PACKAGE_NAME},
                    v.{VariantColumns.VARIANT_NAME}
                FROM {VARIANT_TABLE} AS v
                JOIN {PRODUCT_TABLE} AS p
                    ON p.{ProductColumns.ID} = v.{VariantColumns.PRODUCT_ID}
                WHERE 
                    v.{VariantColumns.VARIANT_NAME} ILIKE %s 
                    AND LOWER(CAST(v.{VariantColumns.IS_ACTIVE} AS TEXT)) = 'true'
                ORDER BY p.{ProductColumns.PACKAGE_NAME}, v.{VariantColumns.VARIANT_NAME}
            """,
        ]

        for sql_query in sql_templates:
            matched_products = db.fetch_all(sql_query, (search_term,))
            if matched_products:
                break
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

    # Tính sẵn giá cao nhất để dùng khi tính bán (không phụ thuộc nguồn đã chọn).
    max_supply_price = None
    if source_prices:
        try:
            max_supply_price = max(Decimal(str(price)) for _, price in source_prices if price is not None)
        except Exception:
            max_supply_price = None
    context.user_data["max_supply_price"] = max_supply_price

    # 2. Xây dựng Keyboard và Map giá
    keyboard, row = [], []
    source_price_map = {} 
    
    for src_name, price in source_prices:
        price_display = f'{int(price):,} đ'.replace(',', '.') if price is not None else "0 đ"
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
