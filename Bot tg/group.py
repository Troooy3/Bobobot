from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database import cursor, conn
from keyboards import settings_menu, user_keyboard
from states import SETTING_PARAM
import logging
from datetime import datetime, timedelta
from os import getenv
from pytz import timezone
import re
import asyncio
import os

logger = logging.getLogger('CryptoBot')
MOSCOW_TZ = timezone('Europe/Moscow')


async def delete_message(chat_id, message_id, context):
    """Удаление сообщения по chat_id и message_id"""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Удалено сообщение с ID {message_id} в чате {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения {message_id}: {e}")


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать текущие настройки"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text="⛔ Эта команда доступна только в группе администраторов!")
        return

    await delete_message(update.message.chat_id, update.message.message_id, context)

    if 'last_bot_message_id' in context.chat_data:
        await delete_message(update.message.chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    cursor.execute('SELECT * FROM settings WHERE id = 1')
    settings = cursor.fetchone()

    settings_text = (
        f"⚙️ Настройки:\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Накрутка: {int(settings[1])}%\n"
        f"🎁 Кэшбэк: {int(settings[2])}%\n"
        f"👥 Рефералы: {int(settings[3])}%\n"
        f"⏳ Время истечения: {settings[10]} мин\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔸 BTC: {int(settings[4])} - {int(settings[7])} RUB\n"
        f"🔹 LTC: {int(settings[5])} - {int(settings[8])} RUB\n"
        f"💲 USDT: {int(settings[6])} - {int(settings[9])} RUB\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✨Что-то необходимо изменить?"
    )
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("📈 Накрутка"), KeyboardButton("🎁 Кэшбэк")],
        [KeyboardButton("👥 Рефералы"), KeyboardButton("🔢 Лимиты")],
        [KeyboardButton("⏳ Время истечения"), KeyboardButton("🔙 Назад")]
    ], resize_keyboard=True)
    message = await context.bot.send_message(chat_id=update.message.chat_id, text=settings_text, reply_markup=keyboard)

    context.chat_data['last_bot_message_id'] = message.message_id
    logger.info(f"Показаны настройки, ID сообщения бота: {message.message_id}")


async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора настройки"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        action = query.data
        chat_id = query.message.chat_id
        msg = query.message
    else:
        action = update.message.text
        chat_id = update.message.chat_id
        msg = update.message

    if chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(chat_id=chat_id, text="⛔ Эта команда доступна только в группе администраторов!")
        return ConversationHandler.END

    await delete_message(chat_id, msg.message_id, context)

    if action not in ["📊 Статистика", "📮 Заявки"] and 'last_bot_message_id' in context.chat_data:
        await delete_message(chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    action_map = {
        "📈 Накрутка": "set_markup",
        "🎁 Кэшбэк": "set_cashback",
        "👥 Рефералы": "set_referral",
        "🔢 Лимиты": "set_limits",
        "⏳ Время истечения": "set_expiration",
        "BTC": "set_limits_btc",
        "LTC": "set_limits_ltc",
        "USDT": "set_limits_usdt"
    }

    if action == "🔙 Назад":
        context.user_data.clear()
        await admin_panel(update, context)
        return ConversationHandler.END
    elif action == "🔢 Лимиты":
        limits_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("BTC"), KeyboardButton("LTC")],
            [KeyboardButton("USDT")],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)
        message = await context.bot.send_message(chat_id, "Выберите валюту для изменения лимитов:",
                                                 reply_markup=limits_keyboard)
        context.chat_data['last_bot_message_id'] = message.message_id
        context.user_data['waiting_for_currency'] = True
        return SETTING_PARAM
    elif action not in action_map:
        return ConversationHandler.END

    setting_type = action_map.get(action)
    context.user_data['setting_type'] = setting_type

    prompts = {
        'set_markup': "📈 Введите процент накрутки (0-100):",
        'set_cashback': "🎁 Введите процент кэшбэка (0-100):",
        'set_referral': "👥 Введите процент рефералов (0-100):",
        'set_limits_btc': "🔸 Введите минимальный и максимальный лимит для BTC (например, 5000 100000):",
        'set_limits_ltc': "🔹 Введите минимальный и максимальный лимит для LTC (например, 5000 100000):",
        'set_limits_usdt': "💲 Введите минимальный и максимальный лимит для USDT (например, 5000 100000):",
        'set_expiration': "⏳ Введите время истечения заявки (в минутах):"
    }

    message = await context.bot.send_message(chat_id, prompts[setting_type])
    context.chat_data['last_bot_message_id'] = message.message_id
    return SETTING_PARAM


async def save_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение настроек"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text="⛔ Эта команда доступна только в группе администраторов!")
        return ConversationHandler.END

    await delete_message(update.message.chat_id, update.message.message_id, context)

    if 'last_bot_message_id' in context.chat_data:
        await delete_message(update.message.chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    setting_type = context.user_data.get('setting_type')
    waiting_for_currency = context.user_data.get('waiting_for_currency', False)

    if not setting_type and not waiting_for_currency:
        message = await context.bot.send_message(chat_id=update.message.chat_id, text="🔄 Сессия устарела")
        context.chat_data['last_bot_message_id'] = message.message_id
        await show_settings(update, context)
        return ConversationHandler.END

    value = update.message.text.strip()

    try:
        if waiting_for_currency:
            if value in ["BTC", "LTC", "USDT"]:
                context.user_data['setting_type'] = f"set_limits_{value.lower()}"
                message = await context.bot.send_message(
                    update.message.chat_id,
                    f"🔢 Введите минимальный и максимальный лимит для {value} (например, 5000 100000):"
                )
                context.chat_data['last_bot_message_id'] = message.message_id
                context.user_data['waiting_for_currency'] = False
                return SETTING_PARAM
            elif value == "🔙 Назад":
                context.user_data.clear()
                await show_settings(update, context)
                return ConversationHandler.END
            else:
                message = await context.bot.send_message(update.message.chat_id, "❌ Выберите валюту из списка!")
                context.chat_data['last_bot_message_id'] = message.message_id
                return SETTING_PARAM

        elif setting_type.startswith('set_limits_'):
            min_a, max_a = map(float, value.split())
            if min_a <= 0 or max_a <= 0:
                raise ValueError("Лимиты должны быть больше 0")
            if min_a >= max_a:
                raise ValueError("Минимум должен быть меньше максимума")
            field_map = {
                'set_limits_btc': ('min_amount_btc', 'max_amount_btc'),
                'set_limits_ltc': ('min_amount_ltc', 'max_amount_ltc'),
                'set_limits_usdt': ('min_amount_usdt', 'max_amount_usdt')
            }
            min_field, max_field = field_map[setting_type]
            cursor.execute(f'UPDATE settings SET {min_field} = ?, {max_field} = ? WHERE id = 1', (min_a, max_a))
            conn.commit()
            crypto = setting_type.split('_')[-1].upper()
            response = f"✅ Лимиты для {crypto} обновлены: {int(min_a)} - {int(max_a)} RUB"
            logger.info(f"Лимиты для {crypto} обновлены: min={min_a}, max={max_a}")
        elif setting_type == 'set_expiration':
            new_value = int(value)
            if new_value <= 0:
                raise ValueError("Время должно быть больше 0")
            cursor.execute('UPDATE settings SET expiration_timeout = ? WHERE id = 1', (new_value,))
            conn.commit()
            response = f"✅ Время истечения обновлено: {new_value} мин"
            logger.info(f"Время истечения обновлено: {new_value} мин")
        else:
            new_value = float(value)
            if not 0 <= new_value <= 100:
                raise ValueError("Значение должно быть от 0 до 100")
            fields = {'set_markup': 'markup_percent', 'set_cashback': 'cashback_percent',
                      'set_referral': 'referral_percent'}
            field = fields[setting_type]
            cursor.execute(f'UPDATE settings SET {field} = ? WHERE id = 1', (new_value,))
            conn.commit()
            response = f"✅ {setting_type.replace('set_', '').capitalize()} обновлен: {new_value}%"
            logger.info(f"Настройка {setting_type} обновлена: {new_value}%")

        message = await context.bot.send_message(update.message.chat_id, response)
        context.chat_data['last_bot_message_id'] = message.message_id
        context.user_data.clear()
        await show_settings(update, context)
        return ConversationHandler.END
    except ValueError as e:
        message = await context.bot.send_message(update.message.chat_id, f"❌ Ошибка: {str(e)}")
        context.chat_data['last_bot_message_id'] = message.message_id
        return SETTING_PARAM
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}")
        message = await context.bot.send_message(update.message.chat_id, "❌ Ошибка сервера")
        context.chat_data['last_bot_message_id'] = message.message_id
        return ConversationHandler.END


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка сообщений в группе: только ID заявок (12 символов)"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        return

    text = update.message.text.strip()

    if not re.match(r'^[a-f0-9]{12}$', text):
        return

    await delete_message(update.message.chat_id, update.message.message_id, context)

    if 'last_bot_message_id' in context.chat_data:
        await delete_message(update.message.chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    public_id = text
    cursor.execute('''
        SELECT o.public_id, u.username, o.amount, o.crypto, 
               o.timestamp, o.wallet_address, o.crypto_amount, o.status, o.expiration_time
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        WHERE o.public_id = ?
    ''', (public_id,))

    if order := cursor.fetchone():
        timestamp = datetime.strptime(str(order[4]), '%Y-%m-%d %H:%M:%S.%f%z')
        expiration_time = timestamp + timedelta(
            minutes=cursor.execute('SELECT expiration_timeout FROM settings WHERE id = 1').fetchone()[0])

        msk_time = timestamp.astimezone(MOSCOW_TZ).strftime('%H:%M MSK')
        expiration_msk = expiration_time.astimezone(MOSCOW_TZ).strftime('%H:%M MSK')

        amount_rub = "{:,.0f}".format(order[2]).replace(',', ' ')
        amount_crypto = "{:.8f}".format(order[6]).rstrip('0').rstrip('.')

        order_text = (
            f"📮 Заявка <code>{order[0]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 @{order[1]}\n"
            f"📭 Адрес: <code>{order[5]}</code>\n\n"
            f"💸 {amount_rub} RUB\n"
            f"🪙 {order[3]}: <code>{amount_crypto}</code>\n\n"
            f"🕒 Создана: {msk_time}\n"
            f"🕒 Срок: {expiration_msk}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔘 Статус: {order[7]}"
        )

        if order[7] == 'pending':
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Одобрить", callback_data=f'approve_{order[0]}'),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_{order[0]}')]
            ])
            message = await context.bot.send_message(
                update.message.chat_id,
                order_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            message = await context.bot.send_message(
                update.message.chat_id,
                order_text,
                parse_mode='HTML'
            )

        context.chat_data['last_bot_message_id'] = message.message_id
    else:
        message = await context.bot.send_message(
            update.message.chat_id,
            f"⚠️ Заявка #{public_id} не найдена или истекла!"
        )
        context.chat_data['last_bot_message_id'] = message.message_id


async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка действий администратора (Inline-кнопки)"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    query = update.callback_query

    if not query:
        logger.error("CallbackQuery отсутствует")
        return

    if query.message.chat_id != GROUP_CHAT_ID:
        logger.error(f"Доступ запрещен: chat_id={query.message.chat_id}, expected={GROUP_CHAT_ID}")
        await query.edit_message_text("⛔ Доступ запрещен!")
        return

    await query.answer()
    action, public_id = query.data.rsplit('_', 1)
    logger.info(f"Получен callback: action={action}, public_id={public_id}, user={query.from_user.id}")

    cursor.execute('''
        SELECT status, user_id, amount, crypto, crypto_amount, bonus_used, wallet_address, expiration_time 
        FROM orders 
        WHERE public_id = ?
    ''', (public_id,))
    order_data = cursor.fetchone()

    if not order_data:
        logger.error(f"Заявка #{public_id} не найдена")
        await query.edit_message_text(f"⚠️ Заявка #{public_id} не найдена")
        return

    status, user_id, amount, crypto, crypto_amount, bonus_used, wallet_address, expiration_time = order_data
    logger.info(f"Заявка #{public_id}: status={status}, user_id={user_id}, amount={amount}")

    cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    if not user_data:
        logger.error(f"Пользователь с ID {user_id} не найден")
        await query.edit_message_text(f"⚠️ Пользователь для заявки #{public_id} не найден")
        return
    username = user_data[0]

    if status != 'pending':
        logger.warning(f"Попытка обработки заявки #{public_id} со статусом {status}")
        await query.edit_message_text(f"ℹ️ Заявка #{public_id} уже обработана ({status})")
        return

    processed_time = datetime.now(MOSCOW_TZ).strftime('%H:%M MSK')
    amount_rub = "{:,.0f}".format(amount).replace(',', ' ')
    amount_crypto = "{:.8f}".format(crypto_amount).rstrip('0').rstrip('.')
    expiration_msk = datetime.strptime(str(expiration_time), '%Y-%m-%d %H:%M:%S.%f%z').astimezone(MOSCOW_TZ).strftime(
        '%H:%M MSK')

    explorer_urls = {
        'BTC': f'https://blockchair.com/bitcoin/address/{wallet_address}',
        'LTC': f'https://blockchair.com/litecoin/address/{wallet_address}/',
        'USDT': f'https://blockchair.com/tron/address/{wallet_address}'
    }
    explorer_link = explorer_urls.get(crypto, '#')

    try:
        if action == 'approve':
            cursor.execute('SELECT cashback_percent, referral_percent FROM settings WHERE id = 1')
            cashback_percent, referral_percent = cursor.fetchone()
            cashback = amount * (cashback_percent / 100)

            cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
            referrer_id = cursor.fetchone()[0]
            referrer_bonus = cashback * (referral_percent / 100) if referrer_id else 0

            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                           (cashback - referrer_bonus, user_id))
            if referrer_id:
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?',
                               (referrer_bonus, referrer_id))
            cursor.execute('UPDATE orders SET status = "completed", processed_time = ? WHERE public_id = ?',
                           (processed_time, public_id))
            conn.commit()

            logger.info(f"Заявка {public_id} успешно подтверждена")
            user_message = (
                f"🌟 Команда TomasExchange благодарит вас за обмен и ждёт снова 🌟\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ Заявка {public_id} подтверждена!\n"
                f"💰 Кэшбэк: {cashback - referrer_bonus:,.0f} RUB\n"
                f"🔗 Проверить кошелек: [Обозреватель]({explorer_link})"
            )
            await context.bot.send_message(user_id, user_message, parse_mode='Markdown')
            if referrer_id:
                await context.bot.send_message(referrer_id, f"🎉 Реферальный бонус: {referrer_bonus:,.0f} RUB")

            full_order_text = (
                f"📮 Заявка {public_id}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 @{username}\n"
                f"📭 Адрес: {wallet_address}\n\n"
                f"💸 {amount_rub} RUB\n"
                f"🪙 {crypto}: {amount_crypto}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✅ Подтверждена: {processed_time}"
            )
            await query.edit_message_text(full_order_text)

            photo_path = os.path.join(os.path.dirname(__file__), 'Photo', 'Tom.png')
            inline_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💻 Оператор", url=f'https://t.me/{getenv("OPERATOR_CHAT")}')],
                [InlineKeyboardButton("💬 Чат", url='https://t.me/TomasExchangeON_Chat')],
                [InlineKeyboardButton("⭐ Отзывы", url='https://t.me/TomasExchangeON_chanell')]
            ])
            try:
                with open(photo_path, 'rb') as photo:
                    await asyncio.wait_for(
                        context.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            reply_markup=inline_keyboard
                        ),
                        timeout=20
                    )
                logger.info("Фото Tom.png отправлено")
            except FileNotFoundError:
                logger.error(f"Файл Tom.png не найден по пути: {photo_path}")
            except asyncio.TimeoutError:
                logger.error("Таймаут при отправке фото Tom.png")
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")

            welcome_text = (
                f"👋 Рады приветствовать Вас снова!\n\n"
                "✨ Выберите действие в меню ниже:"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=welcome_text,
                    reply_markup=user_keyboard()
                )
                logger.info("Приветственное сообщение с главным меню отправлено")
            except Exception as e:
                logger.error(f"Ошибка при отправке приветственного сообщения: {e}")

        elif action == 'reject':
            if bonus_used > 0:
                cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (bonus_used, user_id))
                user_message = (
                    f"❌ Ваша заявка #{public_id} была отклонена.\n"
                    f"Бонусы в размере {bonus_used:,.0f} RUB возвращены."
                )
            else:
                user_message = f"❌ Ваша заявка #{public_id} была отклонена."

            cursor.execute('UPDATE orders SET status = "rejected", processed_time = ? WHERE public_id = ?',
                           (processed_time, public_id))
            conn.commit()
            logger.info(f"Заявка #{public_id} успешно отклонена")

            await context.bot.send_message(user_id, user_message)

            full_order_text = (
                f"📮 Заявка {public_id}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 @{username}\n"
                f"📭 {wallet_address}\n\n"
                f"💸 {amount_rub} RUB\n"
                f"🪙 {crypto}: {amount_crypto}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"❌ Отклонена: {processed_time}"
            )
            await query.edit_message_text(full_order_text)

            photo_path = os.path.join(os.path.dirname(__file__), 'Photo', 'Tom.png')
            inline_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💻 Оператор", url=f'https://t.me/{getenv("OPERATOR_CHAT")}')],
                [InlineKeyboardButton("💬 Чат", url='https://t.me/TomasExchangeON_Chat')],
                [InlineKeyboardButton("⭐ Отзывы", url='https://t.me/TomasExchangeON_chanell')]
            ])
            try:
                with open(photo_path, 'rb') as photo:
                    await asyncio.wait_for(
                        context.bot.send_photo(
                            chat_id=user_id,
                            photo=photo,
                            reply_markup=inline_keyboard
                        ),
                        timeout=20
                    )
                logger.info("Фото Tom.png отправлено")
            except FileNotFoundError:
                logger.error(f"Файл Tom.png не найден по пути: {photo_path}")
            except asyncio.TimeoutError:
                logger.error("Таймаут при отправке фото Tom.png")
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")

            welcome_text = (
                f"👋 Рады приветствовать Вас снова!\n\n"
                "✨ Выберите действие в меню ниже:"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=welcome_text,
                    reply_markup=user_keyboard()
                )
                logger.info("Приветственное сообщение с главным меню отправлено")
            except Exception as e:
                logger.error(f"Ошибка при отправке приветственного сообщения: {e}")

    except Exception as e:
        logger.error(f"Ошибка при обработке заявки #{public_id}: {e}")
        await query.edit_message_text(f"❌ Ошибка при обработке заявки #{public_id}")
        conn.rollback()


async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать активные заявки в группе"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⛔ Эта команда доступна только в группе администраторов!"
        )
        return

    await delete_message(update.message.chat_id, update.message.message_id, context)

    if 'last_bot_message_id' in context.chat_data:
        await delete_message(update.message.chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    cursor.execute('''
        SELECT o.public_id, u.username, o.amount, o.crypto, 
               o.timestamp, o.wallet_address, o.crypto_amount, o.status, o.expiration_time
        FROM orders o 
        JOIN users u ON o.user_id = u.user_id 
        WHERE o.status = 'pending'
    ''')

    admin_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📮 Заявки")]
    ], resize_keyboard=True)

    if orders := cursor.fetchall():
        for order in orders:
            timestamp = datetime.strptime(str(order[4]), '%Y-%m-%d %H:%M:%S.%f%z')
            expiration_time = timestamp + timedelta(minutes=cursor.execute(
                'SELECT expiration_timeout FROM settings WHERE id = 1'
            ).fetchone()[0])

            msk_time = timestamp.astimezone(MOSCOW_TZ).strftime('%H:%M MSK')
            expiration_msk = expiration_time.astimezone(MOSCOW_TZ).strftime('%H:%M MSK')

            amount_rub = "{:,.0f}".format(order[2]).replace(',', ' ')
            amount_crypto = "{:.8f}".format(order[6]).rstrip('0').rstrip('.')

            order_text = (
                f"📮 Заявка <code>{order[0]}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 @{order[1]}\n"
                f"📭 Адрес: <code>{order[5]}</code>\n\n"
                f"💸 {amount_rub} RUB\n"
                f"🪙 {order[3]}: <code>{amount_crypto}</code>\n\n"
                f"🕒 Создана: {msk_time}\n"
                f"🕒 Срок: {expiration_msk}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔘 Статус: {order[7]}"
            )

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Одобрить", callback_data=f'approve_{order[0]}'),
                InlineKeyboardButton("❌ Отклонить", callback_data=f'reject_{order[0]}')
            ]])

            message = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=order_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            context.chat_data['last_bot_message_id'] = message.message_id
    else:
        message = await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="📭 Нет активных заявок",
            reply_markup=admin_keyboard,
            parse_mode='HTML'
        )
        context.chat_data['last_bot_message_id'] = message.message_id


async def show_group_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику системы в группе"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text="⛔ Эта команда доступна только в группе администраторов!")
        return

    await delete_message(update.message.chat_id, update.message.message_id, context)

    cursor.execute('''
        SELECT 
            (SELECT COUNT(*) FROM users),
            (SELECT COUNT(*) FROM orders WHERE status = 'pending'),
            (SELECT COUNT(*) FROM orders WHERE status = 'completed'),
            (SELECT SUM(amount) FROM orders WHERE status = 'completed')
    ''')
    users_count, pending_orders, completed_orders, total_amount = cursor.fetchone()

    stats_text = (
        f"📊 Статистика\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: {users_count}\n"
        f"📮 Активных заявок: {pending_orders}\n"
        f"✅ Завершённых сделок: {completed_orders}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Общий оборот: {total_amount or 0:,.0f} RUB"
    )
    admin_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📮 Заявки")]
    ], resize_keyboard=True)
    message = await context.bot.send_message(chat_id=update.message.chat_id, text=stats_text,
                                             reply_markup=admin_keyboard)
    context.chat_data['last_bot_message_id'] = message.message_id


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ-панель в группе без лишних инструкций"""
    GROUP_CHAT_ID = int(getenv('GROUP_CHAT_ID'))
    if update.message.chat_id != GROUP_CHAT_ID:
        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text="⛔ Эта команда доступна только в группе администраторов!")
        return

    await delete_message(update.message.chat_id, update.message.message_id, context)

    if 'last_bot_message_id' in context.chat_data:
        await delete_message(update.message.chat_id, context.chat_data['last_bot_message_id'], context)
        del context.chat_data['last_bot_message_id']

    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📮 Заявки")]
    ], resize_keyboard=True)
    message = await context.bot.send_message(chat_id=update.message.chat_id, text="Админ-панель:",
                                             reply_markup=keyboard)
    context.chat_data['last_bot_message_id'] = message.message_id