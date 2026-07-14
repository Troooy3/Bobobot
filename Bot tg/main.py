import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
)
from telegram import BotCommand 
from handlers import (
    start, back_handler, start_exchange, select_crypto, select_input_type, 
    process_amount, handle_confirmation_details, handle_wallet, handle_bonus_confirmation,
    menu, restart
)
from group import (
    show_settings, handle_settings, save_settings, handle_group_message, 
    handle_admin_actions, admin_panel, show_group_statistics, show_orders
)
from user import profile, support
from referral import referral_program
from keyboards import user_keyboard, input_type_keyboard
from database import conn, cursor
from states import *
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))

logging.basicConfig(
    format='🎮 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('CryptoBot')
logger.setLevel(logging.DEBUG)

async def set_bot_commands(application):
    """Установка команд в меню бота"""
    commands = [
        BotCommand("menu", "Показать меню/кнопки"),
        BotCommand("restart", "Перезапуск бота, если что-то пошло не так")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Команды /menu и /restart добавлены в меню бота")

def main():
    application = Application.builder().token(TOKEN).build()

    settings_edit_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Chat(chat_id=GROUP_CHAT_ID) & filters.Regex(r'^(📈 Накрутка|🎁 Кэшбэк|👥 Рефералы|🔢 Лимиты|⏳ Время истечения|🔙 Назад)$'), handle_settings),
            CallbackQueryHandler(handle_settings, pattern='^set_')
        ],
        states={
            SETTING_PARAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_settings)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', back_handler)
        ],
        allow_reentry=False,
        conversation_timeout=300
    )

    exchange_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^🔄 Новый обмен$'), start_exchange)],
        states={
            SELECTING_CRYPTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_crypto)],
            SELECTING_INPUT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_input_type)],
            SELECTING_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_amount)],
            CONFIRMING_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bonus_confirmation)],
            CONFIRMING_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation_details),
            ],
            ENTERING_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet)],
        },
        fallbacks=[CommandHandler('cancel', back_handler)],
        conversation_timeout=300
    )

    application.add_handlers([
        CommandHandler('admin', admin_panel),
        MessageHandler(filters.Chat(chat_id=GROUP_CHAT_ID) & filters.Regex(r'^(⚙️ Настройки|📊 Статистика|📮 Заявки)$'), 
                       lambda update, context: show_settings(update, context) if update.message.text == "⚙️ Настройки" 
                       else show_group_statistics(update, context) if update.message.text == "📊 Статистика" 
                       else show_orders(update, context)),
        settings_edit_handler,
        MessageHandler(filters.Chat(chat_id=GROUP_CHAT_ID) & filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^(📈 Накрутка|🎁 Кэшбэк|👥 Рефералы|🔢 Лимиты|⏳ Время истечения|🔙 Назад)$'), handle_group_message),
        CallbackQueryHandler(handle_admin_actions, pattern='^(approve|reject)_'),
        CommandHandler('start', start),
        CommandHandler('menu', menu),
        CommandHandler('restart', restart),
        exchange_handler,
        MessageHandler(filters.Regex(r'^👤 Профиль$'), profile),
        MessageHandler(filters.Regex(r'^📢 Поддержка$'), support),
        MessageHandler(filters.Regex(r'^🎁 Рефералы$'), referral_program),
        MessageHandler(filters.TEXT & ~filters.COMMAND, back_handler)
    ])

    application.post_init = set_bot_commands

    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == '__main__':
    main()