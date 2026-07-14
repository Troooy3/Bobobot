import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database
import config

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = {
    "set_markup": "Установить процент накрутки",
    "set_cashback": "Установить процент кэшбэка",
    "set_referral": "Установить процент реферального вознаграждения",
    "set_min_btc": "Установить мин. BTC",
    "set_max_btc": "Установить макс. BTC",
    "set_min_ltc": "Установить мин. LTC",
    "set_max_ltc": "Установить макс. LTC",
    "set_min_usdt": "Установить мин. USDT",
    "set_max_usdt": "Установить макс. USDT",
    "set_timeout": "Установить время истечения заявки (мин)",
    "stats": "Показать статистику",
    "active_orders": "Список активных заявок",
}

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != config.GROUP_CHAT_ID:
        return
    keyboard = []
    for cmd, desc in ADMIN_COMMANDS.items():
        keyboard.append([InlineKeyboardButton(desc, callback_data=f"admin_{cmd}")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")])
    await update.message.reply_text("⚙️ Админ-панель", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_chat.id != config.GROUP_CHAT_ID:
        await query.edit_message_text("Доступ запрещён.")
        return
    data = query.data
    if data == "admin_close":
        await query.edit_message_text("Панель закрыта.")
        return
    if data.startswith("admin_"):
        cmd = data[6:]
        if cmd in ADMIN_COMMANDS:
            context.user_data['admin_action'] = cmd
            await query.edit_message_text(f"Введите новое значение для '{ADMIN_COMMANDS[cmd]}':")
            return
    # Обработка команд без ввода (stats, active_orders)
    if cmd == "stats":
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
        completed = cursor.fetchone()[0]
        conn.close()
        await query.edit_message_text(
            f"📊 Статистика:\nПользователей: {users}\nАктивных заявок: {pending}\nЗавершённых заявок: {completed}"
        )
    elif cmd == "active_orders":
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, crypto_type, amount_crypto, created_at FROM orders WHERE status='pending'")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            await query.edit_message_text("Нет активных заявок.")
        else:
            msg = "📋 Активные заявки:\n"
            for row in rows:
                msg += f"#{row['id']} | Пользователь {row['user_id']} | {row['crypto_type']} {row['amount_crypto']} | {row['created_at']}\n"
            await query.edit_message_text(msg)

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != config.GROUP_CHAT_ID:
        return
    action = context.user_data.get('admin_action')
    if not action:
        return
    text = update.message.text.strip()
    # Проверка на число для всех, кроме текстовых (но все тут числовые)
    try:
        val = float(text.replace(',', '.'))
        if val < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введите положительное число.")
        return

    conn = database.get_db_connection()
    cursor = conn.cursor()
    # Маппинг действий на поля в таблице settings
    field_map = {
        "set_markup": "markup_percent",
        "set_cashback": "cashback_percent",
        "set_referral": "referral_percent",
        "set_min_btc": "min_btc",
        "set_max_btc": "max_btc",
        "set_min_ltc": "min_ltc",
        "set_max_ltc": "max_ltc",
        "set_min_usdt": "min_usdt",
        "set_max_usdt": "max_usdt",
        "set_timeout": "order_timeout_minutes",
    }
    field = field_map.get(action)
    if not field:
        await update.message.reply_text("Неизвестное действие.")
        return
    cursor.execute(f"UPDATE settings SET {field}=? WHERE id=1", (val,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Значение '{ADMIN_COMMANDS[action]}' установлено на {val}.")
    context.user_data.pop('admin_action', None)
