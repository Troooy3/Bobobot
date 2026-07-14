import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)
import database
import utils
import config
from states import (
    SELECT_CRYPTO, SELECT_INPUT_TYPE, INPUT_AMOUNT, CONFIRM_BONUS,
    INPUT_DETAILS, INPUT_WALLET
)
from keyboards import main_menu_keyboard, crypto_keyboard, input_type_keyboard, confirm_keyboard
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# --- Вспомогательные функции ---
def get_active_orders_count(user_id: int) -> int:
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status='pending'", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_referrer(user_id: int):
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['referrer_id'] if row else None

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    # Регистрация пользователя, если его нет
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        # Обработка реферальной ссылки
        referrer_id = None
        args = context.args
        if args and args[0].isdigit():
            referrer_id = int(args[0])
            if referrer_id == user_id:
                referrer_id = None
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, last_name, referrer_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, user.username, user.first_name, user.last_name, referrer_id)
        )
        conn.commit()
    conn.close()

    # Приветственное сообщение с фото и кнопками
    chat_link = config.CHAT_LINK
    review_link = config.REVIEW_CHANNEL_LINK
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 Связаться с оператором", url=f"https://t.me/{config.OPERATOR_CHAT}")],
        [InlineKeyboardButton("💬 Чат", url=chat_link), InlineKeyboardButton("⭐ Отзывы", url=review_link)]
    ])
    await update.message.reply_photo(
        photo=open("Photo/Tom.png", "rb"),
        caption=f"Привет, {user.first_name}! Добро пожаловать в обменник!",
        reply_markup=keyboard
    )
    await update.message.reply_text("Используйте /menu для основного меню.", reply_markup=main_menu_keyboard())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Состояние сброшено. Используйте /menu.")

# --- Новый обмен (ConversationHandler) ---
async def new_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Проверка активных заявок
    if get_active_orders_count(user_id) >= config.MAX_ACTIVE_ORDERS:
        await update.message.reply_text(f"⚠️ У вас уже есть {config.MAX_ACTIVE_ORDERS} активных заявок. Дождитесь их завершения.")
        return ConversationHandler.END
    await update.message.reply_text("Выберите криптовалюту:", reply_markup=crypto_keyboard())
    return SELECT_CRYPTO

async def select_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    crypto = query.data
    context.user_data['crypto'] = crypto
    await query.edit_message_text("Выберите тип ввода:", reply_markup=input_type_keyboard())
    return SELECT_INPUT_TYPE

async def select_input_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    input_type = query.data  # 'rub' или 'crypto'
    context.user_data['input_type'] = input_type
    await query.edit_message_text("Введите сумму (только число):")
    return INPUT_AMOUNT

async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(',', '.')
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введите корректное положительное число (например, 100.5)")
        return INPUT_AMOUNT

    crypto = context.user_data['crypto']
    input_type = context.user_data['input_type']
    # Проверка лимитов из настроек
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE id=1")
    settings = cursor.fetchone()
    conn.close()
    if not settings:
        await update.message.reply_text("Ошибка настроек. Обратитесь к администратору.")
        return ConversationHandler.END

    min_key = f"min_{crypto.lower()}"
    max_key = f"max_{crypto.lower()}"
    min_val = settings[min_key]
    max_val = settings[max_key]

    if input_type == 'rub':
        # Для рублёвого ввода проверяем лимиты в рублях (курс конвертируется)
        try:
            rate = utils.get_crypto_rate(crypto)
        except Exception as e:
            await update.message.reply_text(f"Ошибка получения курса: {e}")
            return ConversationHandler.END
        amount_crypto = amount / rate
        if amount < min_val or amount > max_val:
            await update.message.reply_text(f"❌ Сумма должна быть от {min_val} до {max_val} RUB.")
            return INPUT_AMOUNT
        context.user_data['amount_rub'] = amount
        context.user_data['amount_crypto'] = amount_crypto
    else:  # в крипте
        if amount < min_val or amount > max_val:
            await update.message.reply_text(f"❌ Сумма должна быть от {min_val} до {max_val} {crypto}.")
            return INPUT_AMOUNT
        context.user_data['amount_crypto'] = amount
        # Рассчитаем рубли (для отображения)
        try:
            rate = utils.get_crypto_rate(crypto)
            context.user_data['amount_rub'] = amount * rate
        except:
            context.user_data['amount_rub'] = 0

    # Проверка бонуса (cashback)
    cashback_percent = settings['cashback_percent']
    if cashback_percent > 0:
        bonus = context.user_data['amount_rub'] * cashback_percent / 100
        context.user_data['bonus'] = bonus
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да", callback_data="confirm_bonus_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="confirm_bonus_no")]
        ])
        await update.message.reply_text(
            f"Вам начисляется кэшбэк {cashback_percent}% = {bonus:.2f} RUB. Подтвердить?",
            reply_markup=keyboard
        )
        return CONFIRM_BONUS
    else:
        context.user_data['bonus'] = 0
        await update.message.reply_text("Введите дополнительные детали (необязательно):")
        return INPUT_DETAILS

async def confirm_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_bonus_no":
        context.user_data['bonus'] = 0
    await query.edit_message_text("Введите дополнительные детали (необязательно):")
    return INPUT_DETAILS

async def input_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['details'] = update.message.text
    await update.message.reply_text("Введите адрес кошелька для получения криптовалюты:")
    return INPUT_WALLET

async def input_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = update.message.text.strip()
    # Простая валидация (можно улучшить)
    if len(wallet) < 10:
        await update.message.reply_text("❌ Адрес слишком короткий. Попробуйте снова.")
        return INPUT_WALLET
    context.user_data['wallet'] = wallet

    # Сохраняем заявку в БД
    user_id = update.effective_user.id
    crypto = context.user_data['crypto']
    amount_rub = context.user_data.get('amount_rub', 0)
    amount_crypto = context.user_data['amount_crypto']
    bonus = context.user_data.get('bonus', 0)
    details = context.user_data.get('details', '')

    # Время истечения
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_timeout_minutes FROM settings WHERE id=1")
    timeout_min = cursor.fetchone()['order_timeout_minutes']
    expires_at = datetime.now() + timedelta(minutes=timeout_min)

    cursor.execute('''
        INSERT INTO orders (user_id, crypto_type, amount_rub, amount_crypto, wallet, bonus, expires_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (user_id, crypto, amount_rub, amount_crypto, wallet, bonus, expires_at))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()

    await update.message.reply_text(
        f"✅ Заявка #{order_id} создана!\n"
        f"Криптовалюта: {crypto}\n"
        f"Сумма: {amount_crypto} {crypto} (≈{amount_rub:.2f} RUB)\n"
        f"Бонус: {bonus:.2f} RUB\n"
        f"Кошелёк: {wallet}\n"
        f"Детали: {details}\n"
        f"Статус: ожидает обработки (истекает {expires_at.strftime('%d.%m.%Y %H:%M')})"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Обмен отменён.")
    return ConversationHandler.END

# --- Регистрация ConversationHandler ---
def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("new_exchange", new_exchange)],
        states={
            SELECT_CRYPTO: [CallbackQueryHandler(select_crypto)],
            SELECT_INPUT_TYPE: [CallbackQueryHandler(select_input_type)],
            INPUT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_amount)],
            CONFIRM_BONUS: [CallbackQueryHandler(confirm_bonus)],
            INPUT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_details)],
            INPUT_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_wallet)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
