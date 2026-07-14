import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import config
import database
import handlers
import group
import referral
from user import profile, support  # предполагается, что эти функции есть в user.py
from keyboards import main_menu_keyboard

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Инициализация БД
    database.init_db()
    logger.info("База данных инициализирована")

    # Создание приложения
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("menu", handlers.menu))
    application.add_handler(CommandHandler("restart", handlers.restart))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("referral", referral.referral_program))
    application.add_handler(CommandHandler("myreferrals", referral.my_referrals))

    # Админ-панель (только в группе)
    application.add_handler(CommandHandler("admin", group.admin_panel))
    application.add_handler(CallbackQueryHandler(group.admin_callback, pattern="^admin_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group.handle_admin_input))

    # ConversationHandler для обмена
    application.add_handler(handlers.get_conversation_handler())

    # Обработка остальных текстовых сообщений (можно добавить)
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ...))

    logger.info("Бот запущен")
    application.run_polling()

if __name__ == "__main__":
    main()
