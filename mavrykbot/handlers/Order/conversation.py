from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .states import (
    STATE_CHON_LOAI_KHACH,
    STATE_NHAP_TEN_SP,
    STATE_CHON_PACKAGE,
    STATE_CHON_PACKAGE_PRODUCT,
    STATE_CHON_MA_SP,
    STATE_CHON_NGUON,
    STATE_NHAP_MA_MOI,
    STATE_NHAP_NGUON_MOI,
    STATE_NHAP_GIA_NHAP,
    STATE_NHAP_THONG_TIN,
    STATE_NHAP_TEN_KHACH,
    STATE_NHAP_LINK_KHACH,
    STATE_NHAP_SLOT,
    STATE_NHAP_GIA_BAN,
    STATE_NHAP_NOTE,
)
from .start import start_add, chon_loai_khach_handler
from .product_selection import (
    nhap_ten_sp_handler,
    chon_package_handler,
    chon_package_product_handler,
    nhap_ma_moi_handler,
    xu_ly_ma_moi_handler,
    chon_ma_sp_handler,
)
from .source_price import (
    chon_nguon_handler,
    chon_nguon_moi_handler,
    nhap_nguon_moi_handler,
    nhap_gia_nhap_handler,
)
from .customer_info import (
    nhap_thong_tin_handler,
    nhap_ten_khach_handler,
    nhap_link_khach_handler,
    nhap_slot_handler,
)
from .pricing import nhap_gia_ban_handler
from .finalize import nhap_note_handler, cancel_add


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
