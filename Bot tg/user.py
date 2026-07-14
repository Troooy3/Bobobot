#user.py
from telegram import Update
from telegram.ext import ContextTypes
from database import cursor
from keyboards import user_keyboard
import logging

logger = logging.getLogger('CryptoBot')

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать профиль пользователя"""
    try:
        user_id = update.effective_user.id
        cursor.execute('''
            SELECT COALESCE(balance, 0), 
                   (SELECT COUNT(*) FROM users WHERE referrer_id = ?), 
                   wallet_address 
            FROM users WHERE user_id = ?
        ''', (user_id, user_id))
        balance, ref_count, wallet = cursor.fetchone()
        
        cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
        cashback_percent = cursor.fetchone()[0]
        
        response = (
            f"👤 Профиль\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Баланс: {balance:.2f} RUB\n"
            f"👥 Приглашено: {ref_count}\n"
            f"🎁 Кэшбэк: {cashback_percent}%\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💼 Кошелек: {wallet or 'не указан'}"
        )
        await update.message.reply_text(response, reply_markup=user_keyboard())
    except Exception as e:
        logger.error(f"Ошибка профиля: {e}")
        await update.message.reply_text("❌ Ошибка загрузки профиля", reply_markup=user_keyboard())

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать контактную информацию поддержки"""
    support_text = (
        f"🆘 Поддержка\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📧 Канал с отзывами: @TomasExchangeON_chanell\n"
        f"💻 Наш чат: @TomasExchangeON_Chat\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Отвечаем в любое время 24/7"
    )
    await update.message.reply_text(support_text, reply_markup=user_keyboard())