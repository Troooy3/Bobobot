import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ID группы администраторов (для админ-панели)
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", 0))

# Ссылки на чат/канал (вынесены в .env)
CHAT_LINK = os.getenv("CHAT_LINK", "https://t.me/your_chat")
REVIEW_CHANNEL_LINK = os.getenv("REVIEW_CHANNEL_LINK", "https://t.me/your_channel")
OPERATOR_CHAT = os.getenv("OPERATOR_CHAT", "@operator")

# Настройки базы данных
DB_FILE = "crypto_bot.db"

# Время кеширования курса (секунды)
CACHE_TIMEOUT = 60

# Максимальное количество активных заявок на пользователя
MAX_ACTIVE_ORDERS = 3
