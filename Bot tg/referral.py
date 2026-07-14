#referral.py
from telegram import Update
from telegram.ext import ContextTypes
from database import cursor
from keyboards import user_keyboard
import logging

logger = logging.getLogger('CryptoBot')

async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать информацию о реферальной программе"""
    try:
        user_id = update.effective_user.id
        cursor.execute('SELECT referral_percent FROM settings WHERE id = 1')
        referral_percent = int(cursor.fetchone()[0])
        
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(o.amount * (s.cashback_percent/100) * (s.referral_percent/100)) 
            FROM users u 
            LEFT JOIN orders o ON u.user_id = o.user_id 
            LEFT JOIN settings s ON 1=1 
            WHERE u.referrer_id = ? AND o.status = 'completed'
        ''', (user_id,))
        ref_count, total_earnings = cursor.fetchone()
        total_earnings = total_earnings or 0
        
        response = (
            f"👥 Реферальная программа\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Приглашено: {ref_count}\n"
            f"💎 Бонус: {referral_percent}% от кэшбэка\n"
            f"💰 Заработано: {int(total_earnings)} RUB\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔗 Ссылка: {ref_link}\n"
        )
        await update.message.reply_text(response, reply_markup=user_keyboard())
    except Exception as e:
        logger.error(f"Ошибка рефералов: {e}")
        await update.message.reply_text("❌ Ошибка загрузки", reply_markup=user_keyboard())