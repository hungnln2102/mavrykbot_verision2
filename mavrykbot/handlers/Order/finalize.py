import asyncio
import logging
import requests
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest

from mavrykbot.core.utils import escape_mdv2
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import ORDER_LIST_TABLE, OrderListColumns
from mavrykbot.core.order_status import ORDER_STATUS_UNPAID
from mavrykbot.core.id_service import get_next_id
from mavrykbot.handlers.menu import show_main_selector

from .utils import safe_edit_md, safe_send_md, md, tinh_ngay_het_han

logger = logging.getLogger(__name__)


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
        

        # Ghi vao PostgreSQL
        try:
            # Get next ID from database to ensure consistency with web backend
            next_id = get_next_id(ORDER_LIST_TABLE, OrderListColumns.ID)
            
            sql_query = f"""
                INSERT INTO {ORDER_LIST_TABLE} (
                    {OrderListColumns.ID}, {OrderListColumns.ID_DON_HANG}, {OrderListColumns.SAN_PHAM},
                    {OrderListColumns.THONG_TIN_SAN_PHAM}, {OrderListColumns.KHACH_HANG},
                    {OrderListColumns.LINK_LIEN_HE}, {OrderListColumns.SLOT},
                    {OrderListColumns.NGAY_DANG_KI}, {OrderListColumns.SO_NGAY_DA_DANG_KI},
                    {OrderListColumns.HET_HAN}, {OrderListColumns.NGUON},
                    {OrderListColumns.GIA_NHAP}, {OrderListColumns.GIA_BAN},
                    {OrderListColumns.NOTE}, {OrderListColumns.TINH_TRANG}
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT ({OrderListColumns.ID}) 
                DO UPDATE SET
                    {OrderListColumns.ID_DON_HANG} = EXCLUDED.{OrderListColumns.ID_DON_HANG},
                    {OrderListColumns.SAN_PHAM} = EXCLUDED.{OrderListColumns.SAN_PHAM},
                    {OrderListColumns.THONG_TIN_SAN_PHAM} = EXCLUDED.{OrderListColumns.THONG_TIN_SAN_PHAM},
                    {OrderListColumns.KHACH_HANG} = EXCLUDED.{OrderListColumns.KHACH_HANG},
                    {OrderListColumns.LINK_LIEN_HE} = EXCLUDED.{OrderListColumns.LINK_LIEN_HE},
                    {OrderListColumns.SLOT} = EXCLUDED.{OrderListColumns.SLOT},
                    {OrderListColumns.NGAY_DANG_KI} = EXCLUDED.{OrderListColumns.NGAY_DANG_KI},
                    {OrderListColumns.SO_NGAY_DA_DANG_KI} = EXCLUDED.{OrderListColumns.SO_NGAY_DA_DANG_KI},
                    {OrderListColumns.HET_HAN} = EXCLUDED.{OrderListColumns.HET_HAN},
                    {OrderListColumns.NGUON} = EXCLUDED.{OrderListColumns.NGUON},
                    {OrderListColumns.GIA_NHAP} = EXCLUDED.{OrderListColumns.GIA_NHAP},
                    {OrderListColumns.GIA_BAN} = EXCLUDED.{OrderListColumns.GIA_BAN},
                    {OrderListColumns.NOTE} = EXCLUDED.{OrderListColumns.NOTE},
                    {OrderListColumns.TINH_TRANG} = EXCLUDED.{OrderListColumns.TINH_TRANG}
            """

            params = (
                next_id,
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
                ORDER_STATUS_UNPAID,
            )

            db.execute(sql_query, params)
            logger.info("Inserted/Updated order ID=%s, order_code=%s into order_list", next_id, params[1])

        except Exception as e:
            logger.error(f"Loi khi ghi don hang vao PostgreSQL: {e}", exc_info=True)
            await safe_send_md(
                context.bot,
                chat_id,
                md(f"Can not insert order to PostgreSQL: {e}"),
                try_plain=True,
            )
            return await end_add(update, context, success=False)

        ma_don_final = info.get('ma_don','')
        
        # Format giá bán với dấu chấm phân cách
        gia_ban_formatted = f"{gia_ban_value:,} đ".replace(',', '.')
        
        # Tạo caption với format đẹp, không dùng MarkdownV2
        caption = (
            f"✅ Đơn hàng {ma_don_final} đã được tạo thành công!\n\n"
            f"📦 THÔNG TIN SẢN PHẨM\n"
            f"🔹 Tên Sản Phẩm: {info.get('ma_chon', '')}\n"
            f"📝 Thông Tin Đơn Hàng: {info.get('thong_tin_don', '')}\n"
            f"📆 Ngày Bắt đầu: {ngay_bat_dau_str}\n"
            f"⏳ Thời hạn: {so_ngay} ngày\n"
            f"📅 Ngày Hết hạn: {ngay_het_han_dt.strftime('%d/%m/%Y') if ngay_het_han_dt else 'N/A'}\n"
            f"💵 Giá bán: {gia_ban_formatted}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"👤 THÔNG TIN KHÁCH HÀNG\n"
            f"🔸 Tên Khách Hàng: {info.get('khach_hang', '')}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"📢 HƯỚNG DẪN THANH TOÁN\n"
            f"📢 STK: 9183400998\n"
            f"📢 Nội dung: Thanh toán {ma_don_final}"
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
        
        # Send photo with plain text caption (no markdown)
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
