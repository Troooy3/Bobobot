#keyboards.py
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton

def user_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура пользователя"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔄 Новый обмен"), KeyboardButton("👤 Профиль")],
        [KeyboardButton("🎁 Рефералы"), KeyboardButton("📢 Поддержка")]
    ], resize_keyboard=True)

def admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура администратора"""
    return ReplyKeyboardMarkup([
        [KeyboardButton("📮 Активные заявки"), KeyboardButton("⚙️ Настройки")],
        [KeyboardButton("📊 Статистика")]
    ], resize_keyboard=True)

def input_type_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора типа ввода"""
    return ReplyKeyboardMarkup([
        ["💵 В рублях", "🪙 В крипте"],
        ["🔙 Назад"]
    ], resize_keyboard=True)

def settings_menu() -> InlineKeyboardMarkup:
    """Меню настроек администратора"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Накрутка", callback_data='set_markup'),
         InlineKeyboardButton("🎁 Кэшбэк", callback_data='set_cashback')],
        [InlineKeyboardButton("👥 Рефералы", callback_data='set_referral'),
         InlineKeyboardButton("🔢 Лимиты", callback_data='set_limits')]
    ])