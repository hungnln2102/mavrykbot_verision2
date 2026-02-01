"""Conversation handler builder for update order flow."""
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from mavrykbot.handlers.UpdateOrder.actions import delete_order, extend_order
from mavrykbot.handlers.UpdateOrder.edit_handlers import (
    back_to_order_display,
    choose_field_to_edit,
    input_new_link_khach_handler,
    input_new_nguon_handler,
    input_new_simple_value_handler,
    input_new_so_ngay_handler,
    input_new_ten_khach_handler,
    skip_link_after_name_handler,
    skip_link_khach_handler,
    start_edit_update,
)
from mavrykbot.handlers.UpdateOrder.navigation import (
    cancel_update,
    input_value_handler,
    select_check_mode,
    show_matched_order,
    start_update_order,
)
from mavrykbot.handlers.UpdateOrder.states import (
    EDIT_CHOOSE_FIELD,
    EDIT_INPUT_LINK_KHACH,
    EDIT_INPUT_NGUON,
    EDIT_INPUT_SIMPLE,
    EDIT_INPUT_SO_NGAY,
    EDIT_INPUT_TEN_KHACH,
    INPUT_VALUE,
    SELECT_ACTION,
    SELECT_MODE,
)


def get_update_order_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("update", start_update_order),
            CallbackQueryHandler(start_update_order, pattern="^update$"),
        ],
        states={
            SELECT_MODE: [
                CallbackQueryHandler(select_check_mode, pattern="^mode_.*$"),
            ],
            INPUT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_value_handler)
            ],
            SELECT_ACTION: [
                CallbackQueryHandler(cancel_update, pattern="^cancel_update$"),
                CallbackQueryHandler(
                    lambda u, c: show_matched_order(u, c, "prev"),
                    pattern="^nav_prev$",
                ),
                CallbackQueryHandler(
                    lambda u, c: show_matched_order(u, c, "next"),
                    pattern="^nav_next$",
                ),
                CallbackQueryHandler(extend_order, pattern=r"^action_extend\|"),
                CallbackQueryHandler(delete_order, pattern=r"^action_delete\|"),
                CallbackQueryHandler(start_edit_update, pattern=r"^action_edit\|"),
            ],
            EDIT_CHOOSE_FIELD: [
                CallbackQueryHandler(choose_field_to_edit, pattern=r"^edit\|"),
                CallbackQueryHandler(back_to_order_display, pattern="^back_to_order$"),
            ],
            EDIT_INPUT_SIMPLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_simple_value_handler
                )
            ],
            EDIT_INPUT_NGUON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_new_nguon_handler)
            ],
            EDIT_INPUT_SO_NGAY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_so_ngay_handler
                )
            ],
            EDIT_INPUT_TEN_KHACH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_ten_khach_handler
                )
            ],
            EDIT_INPUT_LINK_KHACH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, input_new_link_khach_handler
                ),
                CallbackQueryHandler(skip_link_khach_handler, pattern="^skip_link_khach$"),
                CallbackQueryHandler(skip_link_after_name_handler, pattern="^skip_link_after_name$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_update, pattern="^cancel_update$"),
            CommandHandler("cancel", cancel_update),
        ],
        name="update_order_conversation",
        persistent=False,
        allow_reentry=True,
    )
