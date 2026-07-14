import asyncio
from telegram.error import TimedOut
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database import cursor, conn
from utils import generate_public_id, get_crypto_rate, validate_wallet, get_example_address
from keyboards import user_keyboard, input_type_keyboard
from states import *
from decimal import Decimal, InvalidOperation
import logging
from datetime import datetime, timedelta
from os import getenv
import os
from pytz import timezone

logger = logging.getLogger('CryptoBot')
MOSCOW_TZ = timezone('Europe/Moscow')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка команды /start для всех пользователей"""
    user = update.effective_user

    photo_path = os.path.join(os.path.dirname(__file__), 'Photo', 'Tom.png')
    inline_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Оператор", url=f'https://t.me/{getenv("OPERATOR_CHAT")}')],
        [InlineKeyboardButton("💬 Чат", url='https://t.me/TomasExchangeON_Chat')],
        [InlineKeyboardButton("⭐ Отзывы", url='https://t.me/TomasExchangeON_chanell')]
    ])
    await update.message.reply_photo(photo=photo_path, reply_markup=inline_keyboard)

    welcome_text = (
        f"👋 Добро пожаловать, {user.first_name}\n\n"
        "✨ Выберите действие в меню ниже:"
    )
    await update.message.reply_text(welcome_text, reply_markup=user_keyboard())

    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (referrer_id,))
        if not cursor.fetchone():
            referrer_id = None

    cursor.execute('SELECT user_id, referrer_id FROM users WHERE user_id = ?', (user.id,))
    existing_user = cursor.fetchone()

    if existing_user:
        if referrer_id and not existing_user[1]:
            cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user.id))
            conn.commit()
            await notify_referrer(context, referrer_id, user)
    else:
        cursor.execute(
            'INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)',
            (user.id, user.username, referrer_id)
        )
        conn.commit()
        if referrer_id:
            await notify_referrer(context, referrer_id, user)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка команды /menu - показывает меню с кнопками"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вызвал /menu")

    welcome_text = (
        f"👋 {user.first_name}, вот ваше меню! ✨\n\n"
        "✨ Выберите действие в меню ниже:"
    )
    await update.message.reply_text(welcome_text, reply_markup=user_keyboard())


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команды /restart - перезапуск диалога"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} вызвал /restart")
    context.user_data.clear()
    await update.message.reply_text("🔄 Бот перезапущен.", reply_markup=user_keyboard())
    return ConversationHandler.END


async def notify_referrer(context: ContextTypes.DEFAULT_TYPE, referrer_id: int, user) -> None:
    try:
        await context.bot.send_message(
            referrer_id,
            f"🎉 Новый реферал зарегистрирован!\n👤 Пользователь: @{user.username}"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления реферера: {e}")


async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Возврат в главное меню"""
    await update.message.reply_text("🔙 Главное меню", reply_markup=user_keyboard())
    return ConversationHandler.END


async def start_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало нового обмена с отображением лимитов для каждой валюты"""
    OPERATOR_CHAT = os.getenv('OPERATOR_CHAT', '@MySupportGroup')
    operator_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍💻 Оператор", url=f'https://t.me/{OPERATOR_CHAT}' if not OPERATOR_CHAT.startswith(
            'http') else OPERATOR_CHAT)]
    ])
    await update.message.reply_text(
        "🔄 По всем вопросам обращаться:",
        reply_markup=operator_button
    )

    cursor.execute(
        'SELECT min_amount_btc, min_amount_ltc, min_amount_usdt, max_amount_btc, max_amount_ltc, max_amount_usdt FROM settings WHERE id = 1')
    min_btc, min_ltc, min_usdt, max_btc, max_ltc, max_usdt = map(Decimal, cursor.fetchone())

    limits_text = (
        f"📊 Текущие лимиты для обмена:\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔸 BTC: {min_btc:,.0f} RUB\n"
        f"🔹 LTC: {min_ltc:,.0f} RUB\n"
        f"💲 USDT: {min_usdt:,.0f} RUB\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        "💱 Выберите валюту:"
    )

    crypto_keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🔸 BTC"), KeyboardButton("🔹 LTC"), KeyboardButton("💲 USDT")],
        [KeyboardButton("🔙 На главную")]
    ], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(limits_text, reply_markup=crypto_keyboard)
    context.user_data.clear()
    return SELECTING_CRYPTO


async def select_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    crypto_map = {"🔸 BTC": "BTC", "🔹 LTC": "LTC", "💲 USDT": "USDT"}
    text = update.message.text
    if text == "🔙 На главную":
        await back_handler(update, context)
        return ConversationHandler.END

    if text not in crypto_map:
        await update.message.reply_text(
            "❌ Выберите валюту из предложенных:",
            reply_markup=ReplyKeyboardMarkup([["🔸 BTC", "🔹 LTC", "💲 USDT"], ["🔙 На главную"]], resize_keyboard=True)
        )
        return SELECTING_CRYPTO

    context.user_data['crypto'] = crypto_map[text]
    await update.message.reply_text("💡 Выберите способ ввода суммы:", reply_markup=input_type_keyboard())
    return SELECTING_INPUT_TYPE


async def select_input_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text == "🔙 Назад":
        await update.message.reply_text(
            "💱 Выберите валюту:",
            reply_markup=ReplyKeyboardMarkup([["🔸 BTC", "🔹 LTC", "💲 USDT"], ["🔙 На главную"]], resize_keyboard=True)
        )
        return SELECTING_CRYPTO

    if 'crypto' not in context.user_data:
        await update.message.reply_text("❌ Сначала выберите валюту!")
        return SELECTING_CRYPTO

    crypto = context.user_data['crypto']
    cursor.execute(
        'SELECT min_amount_btc, min_amount_ltc, min_amount_usdt, max_amount_btc, max_amount_ltc, max_amount_usdt FROM settings WHERE id = 1')
    min_btc, min_ltc, min_usdt, max_btc, max_ltc, max_usdt = map(Decimal, cursor.fetchone())
    min_rub = {'BTC': min_btc, 'LTC': min_ltc, 'USDT': min_usdt}[crypto]
    max_rub = {'BTC': max_btc, 'LTC': max_ltc, 'USDT': max_usdt}[crypto]
    rate = Decimal(get_crypto_rate(crypto))
    min_crypto = min_rub / rate
    max_crypto = max_rub / rate

    if text == "💵 В рублях":
        context.user_data['input_type'] = 'RUB'
        prompt = f"💵 Введите сумму в RUB\n📏 Лимиты: {min_rub:,.0f} - {max_rub:,.0f} RUB"
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("🔙 Назад"), KeyboardButton("🔻 Минимальный обмен")]
        ], resize_keyboard=True)
    elif text == "🪙 В крипте":
        context.user_data['input_type'] = 'CRYPTO'
        prompt = f"🪙 Введите количество {crypto}\n📏 Лимиты: {min_crypto:.8f} - {max_crypto:.8f} {crypto}"
        keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("🔙 Назад"), KeyboardButton("🔻 Минимальный обмен")]
        ], resize_keyboard=True)
    else:
        await update.message.reply_text("❌ Неверный выбор!", reply_markup=input_type_keyboard())
        return SELECTING_INPUT_TYPE

    await update.message.reply_text(prompt, reply_markup=keyboard)
    return SELECTING_AMOUNT


async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        if 'crypto' not in context.user_data:
            await update.message.reply_text("❌ Сначала выберите валюту!")
            await update.message.reply_text(
                "💱 Выберите валюту:",
                reply_markup=ReplyKeyboardMarkup([["🔸 BTC", "🔹 LTC", "💲 USDT"], ["🔙 На главную"]], resize_keyboard=True)
            )
            return SELECTING_CRYPTO

        user_input = update.message.text.replace(',', '.').strip()
        crypto = context.user_data['crypto']
        rate = Decimal(str(get_crypto_rate(crypto)))
        cursor.execute(
            'SELECT markup_percent, min_amount_btc, min_amount_ltc, min_amount_usdt, max_amount_btc, max_amount_ltc, max_amount_usdt FROM settings WHERE id = 1')
        markup_percent, min_btc, min_ltc, min_usdt, max_btc, max_ltc, max_usdt = cursor.fetchone()
        min_rub = Decimal(str({'BTC': min_btc, 'LTC': min_ltc, 'USDT': min_usdt}[crypto]))
        max_rub = Decimal(str({'BTC': max_btc, 'LTC': max_ltc, 'USDT': max_usdt}[crypto]))
        markup = Decimal(str(markup_percent)) / Decimal('100')
        final_rate = rate * (Decimal('1') + markup)

        if user_input == "🔙 Назад":
            await update.message.reply_text("💡 Выберите способ ввода суммы:", reply_markup=input_type_keyboard())
            return SELECTING_INPUT_TYPE
        elif user_input == "🔻 Минимальный обмен":
            rub_amount = min_rub
            crypto_amount = rub_amount / final_rate
        else:
            amount = Decimal(user_input)
            input_type = context.user_data['input_type']
            if input_type == 'RUB':
                rub_amount = amount
                crypto_amount = rub_amount / final_rate
            else:
                crypto_amount = amount
                rub_amount = crypto_amount * final_rate

        if not (min_rub <= rub_amount <= max_rub):
            await update.message.reply_text(
                f"⚠️ Сумма должна быть от {min_rub:,.0f} до {max_rub:,.0f} RUB\nТекущая сумма: {rub_amount:,.2f} RUB"
            )
            return SELECTING_AMOUNT

        context.user_data.update({
            'amount': float(rub_amount),
            'crypto_amount': float(crypto_amount),
            'rate': float(rate),
            'markup': float(markup * 100)
        })

        user_id = update.effective_user.id
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        bonus_balance = cursor.fetchone()[0]

        if bonus_balance > 0:
            await update.message.reply_text(
                f"💰 У вас есть {bonus_balance:.2f} RUB\n"
                f"🌟 Хотите ли вы их списать?",
                reply_markup=ReplyKeyboardMarkup([["💼 Копить", "💸 Списать"]], resize_keyboard=True)
            )
            return CONFIRMING_BONUS
        else:
            await update.message.reply_text("😔 У вас нет бонусов для списания")
            cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
            cashback_percent = Decimal(str(cursor.fetchone()[0]))
            cashback_amount = rub_amount * (cashback_percent / Decimal('100'))
            crypto_emoji = {'BTC': '🔸', 'LTC': '🔹', 'USDT': '💲'}[crypto]
            order_text = (
                f"📝 Детали обмена\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{crypto_emoji} Криптовалюта: {crypto}\n"
                f"💵 К получению: {crypto_amount:.8f} {crypto}\n"
                f"💸 К оплате: {rub_amount:,.0f} RUB\n"
                f"🎁 Кэшбэк: {float(cashback_percent)}% ({cashback_amount:,.0f} RUB)\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🌟Всё верно?"
            )
            await update.message.reply_text(
                order_text,
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад"), KeyboardButton("✅ Верно")]],
                                                 resize_keyboard=True)
            )
            return CONFIRMING_DETAILS

    except (ValueError, InvalidOperation):
        await update.message.reply_text("❌ Введите корректное число (например, 1000 или 1000.50)!")
        return SELECTING_AMOUNT
    except Exception as e:
        logger.error(f"Ошибка в process_amount: {e}")
        await update.message.reply_text("❌ Произошла ошибка, попробуйте начать заново.")
        return SELECTING_CRYPTO


async def handle_bonus_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id

    if text == "💸 Списать":
        context.user_data['use_bonus'] = True
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = Decimal(str(cursor.fetchone()[0]))
        max_bonus_allowed = Decimal(str(context.user_data['amount'])) * Decimal('0.8')
        bonus_to_use = min(balance, max_bonus_allowed)
        context.user_data['bonus_to_use'] = float(bonus_to_use)
        remaining_balance = balance - bonus_to_use
        amount_with_bonus = Decimal(str(context.user_data['amount'])) - Decimal(str(bonus_to_use))
        context.user_data['amount_with_bonus'] = float(amount_with_bonus)  # Сохраняем в context.user_data
        message = (
            f"💸 Списано {bonus_to_use:.0f} RUB\n"
            f"💡 (максимум 80% от суммы)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 Новая сумма к оплате: {amount_with_bonus:.0f} RUB.\n"
            f"💰 Остаток: {remaining_balance:.0f} RUB"
        )
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад"), KeyboardButton("✅ Верно")]],
                                             resize_keyboard=True)
        )
    elif text == "💼 Копить":
        context.user_data['use_bonus'] = False
        context.user_data['bonus_to_use'] = 0
        context.user_data['amount_with_bonus'] = float(context.user_data['amount'])  # Сохраняем без бонуса
        await update.message.reply_text(
            "ℹ️ Бонусы не будут списаны.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад"), KeyboardButton("✅ Верно")]],
                                             resize_keyboard=True)
        )
    else:
        await update.message.reply_text("❌ Неверный выбор. Выберите '💸 Списать' или '💼 Копить'.")
        return CONFIRMING_BONUS

    crypto = context.user_data['crypto']
    cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
    cashback_percent = Decimal(str(cursor.fetchone()[0]))
    amount_with_bonus = Decimal(str(context.user_data['amount_with_bonus']))
    cashback_amount = amount_with_bonus * (cashback_percent / Decimal('100'))
    crypto_emoji = {'BTC': '🔸', 'LTC': '🔹', 'USDT': '💲'}[crypto]
    order_text = (
        f"📝 Детали обмена\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{crypto_emoji} Криптовалюта: {crypto}\n"
        f"💵 К получению: {context.user_data['crypto_amount']:.8f} {crypto}\n\n"
        f"💸 К оплате: {amount_with_bonus:,.0f} RUB\n"
        f"🎁 Кэшбэк: {float(cashback_percent)}% ({cashback_amount:,.0f} RUB)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌟Всё верно?"
    )
    await update.message.reply_text(
        order_text,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад"), KeyboardButton("✅ Верно")]], resize_keyboard=True)
    )
    return CONFIRMING_DETAILS


async def handle_confirmation_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    user_id = update.effective_user.id
    logger.info(f"handle_confirmation_details вызвана с текстом: {text}")

    if text in ["🔄 Новый обмен", "👤 Профиль", "🎁 Рефералы", "📢 Поддержка"]:
        await update.message.reply_text("🔙 Главное меню", reply_markup=user_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    if text == "🔙 Назад":
        if 'crypto' not in context.user_data:
            await update.message.reply_text("❌ Сначала выберите валюту!")
            return SELECTING_CRYPTO
        crypto = context.user_data['crypto']
        input_type = context.user_data['input_type']
        cursor.execute(
            'SELECT min_amount_btc, min_amount_ltc, min_amount_usdt, max_amount_btc, max_amount_ltc, max_amount_usdt FROM settings WHERE id = 1')
        min_btc, min_ltc, min_usdt, max_btc, max_ltc, max_usdt = map(Decimal, cursor.fetchone())
        min_rub = {'BTC': min_btc, 'LTC': min_ltc, 'USDT': min_usdt}[crypto]
        max_rub = {'BTC': max_btc, 'LTC': max_ltc, 'USDT': max_usdt}[crypto]
        rate = Decimal(get_crypto_rate(crypto))
        min_crypto = min_rub / rate
        max_crypto = max_rub / rate

        prompt = (
            f"💵 Введите сумму в RUB\n📏 Лимиты: {min_rub:,.0f} - {max_rub:,.0f} RUB" if input_type == 'RUB' else
            f"🪙 Введите количество {crypto}\n📏 Лимиты: {min_crypto:.8f} - {max_crypto:.8f} {crypto}"
        )
        await update.message.reply_text(prompt, reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад")]],
                                                                                 resize_keyboard=True))
        logger.info("Возврат к SELECTING_AMOUNT")
        return SELECTING_AMOUNT

    if text == "✅ Верно":
        crypto = context.user_data['crypto']
        cursor.execute('SELECT wallet_address FROM users WHERE user_id = ?', (user_id,))
        saved_wallet = cursor.fetchone()[0]

        keyboard_buttons = [[KeyboardButton("🔙 Назад"), KeyboardButton("💾 Сохраненный")]] if saved_wallet else [
            [KeyboardButton("🔙 Назад")]]

        await update.message.reply_text(
            f"⚙️ Введите адрес {crypto} кошелька:\n\n💡 Примеры:\n{get_example_address(crypto)}",
            reply_markup=ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
        )
        logger.info("Переход к ENTERING_WALLET")
        return ENTERING_WALLET

    if text in ["💾 Сохранить адрес", "🚀 Продолжить без сохранения"]:
        wallet = context.user_data.get('wallet')
        if wallet and validate_wallet(wallet, context.user_data['crypto']):
            if text == "💾 Сохранить адрес":
                cursor.execute('UPDATE users SET wallet_address = ? WHERE user_id = ?', (wallet, user_id))
                conn.commit()
                await update.message.reply_text("✅ Адрес сохранен!")
            logger.info("Вызов process_valid_wallet")
            return await process_valid_wallet(update, context)
        else:
            await update.message.reply_text("❌ Неверный адрес кошелька")
            logger.info("Возврат к ENTERING_WALLET из-за неверного адреса")
            return ENTERING_WALLET

    if text == "✅ Создать":
        logger.info("Нажата кнопка '✅ Создать'")
        OPERATOR_CHAT = os.getenv('OPERATOR_CHAT', '@MySupportGroup')
        public_id = generate_public_id()
        cursor.execute('SELECT expiration_timeout FROM settings WHERE id = 1')
        expiration_timeout = cursor.fetchone()[0]
        bonus_to_use = context.user_data.get('bonus_to_use', 0)

        timestamp = datetime.now(MOSCOW_TZ)
        expiration_time = timestamp + timedelta(minutes=expiration_timeout)

        if context.user_data.get('use_bonus', False) and bonus_to_use > 0:
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            balance = Decimal(str(cursor.fetchone()[0]))
            if balance >= Decimal(str(bonus_to_use)):
                cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (bonus_to_use, user_id))
                conn.commit()
                logger.info(f"Списано {bonus_to_use:.0f} RUB бонусов с пользователя {user_id} для заявки #{public_id}")
                new_amount = context.user_data['amount'] - bonus_to_use
                context.user_data['amount'] = new_amount
            else:
                await update.message.reply_text("❌ Недостаточно бонусов для списания.")
                return ConversationHandler.END

        cursor.execute('''
            INSERT INTO orders (
                user_id, crypto, amount, crypto_amount, rate, markup, status, 
                wallet_address, timestamp, expiration_time, public_id, bonus_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            context.user_data['crypto'],
            context.user_data['amount'],
            context.user_data['crypto_amount'],
            context.user_data['rate'],
            context.user_data['markup'],
            'pending',
            context.user_data['wallet'],
            timestamp,
            expiration_time,
            public_id,
            bonus_to_use
        ))
        conn.commit()
        logger.info(f"Создана заявка #{public_id} с bonus_used={bonus_to_use}")

        amount_rub = "{:,.0f}".format(context.user_data['amount']).replace(',', ' ')
        amount_crypto = "{:.8f}".format(context.user_data['crypto_amount']).rstrip('0').rstrip('.')
        cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
        cashback_percent = Decimal(str(cursor.fetchone()[0]))
        cashback_amount = Decimal(str(context.user_data['amount'])) * (cashback_percent / Decimal('100'))
        crypto_emoji = {'BTC': '🔸', 'LTC': '🔹', 'USDT': '💲'}[context.user_data['crypto']]

        order_text = (
            f"✅ Заявка успешно создана!\n\n"
            f"🔖 Номер: `{public_id}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏁 Адрес получения: `{context.user_data['wallet']}`\n\n"
            f"{crypto_emoji} Криптовалюта: {context.user_data['crypto']}\n"
            f"💵 К получению: {amount_crypto} {context.user_data['crypto']}\n\n"
            f"💸 К оплате: {amount_rub} RUB\n"
            f"🎁 Кэшбэк: {float(cashback_percent)}% ({cashback_amount:,.0f} RUB)\n\n"
            f"⏳ Заявка действительна до: {expiration_time.strftime('%H:%M MSK')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔄 Для получения реквизитов - перешлите заявку оператору"
        )

        operator_button = InlineKeyboardMarkup([[
            InlineKeyboardButton("👨‍💻 Оператор", url=f'https://t.me/{OPERATOR_CHAT}' if not OPERATOR_CHAT.startswith(
                'http') else OPERATOR_CHAT)]
        ])
        await update.message.reply_text(order_text, reply_markup=operator_button, parse_mode='Markdown')
        logger.info("Отправлено сообщение с деталями заявки")

        context.job_queue.run_once(check_order_expiration, expiration_timeout * 60,
                                   data={'public_id': public_id, 'user_id': user_id})

        logger.info("Заявка создана, процесс завершен")
        context.user_data.clear()
        return ConversationHandler.END

    elif text == "❌ Отменить":
        logger.info("Нажата кнопка '❌ Отменить'")
        await update.message.reply_text("❌ Создание заявки отменено", reply_markup=user_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    logger.warning(f"Неизвестный текст в handle_confirmation_details: {text}")
    return CONFIRMING_DETAILS


async def handle_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = update.message.text.strip()
    crypto = context.user_data['crypto']

    cursor.execute('SELECT wallet_address FROM users WHERE user_id = ?', (user_id,))
    saved_wallet = cursor.fetchone()[0]

    if text == "💾 Сохраненный" and saved_wallet:
        context.user_data['wallet'] = saved_wallet
        await update.message.reply_text(f"✅ Использован сохраненный кошелек:\n {saved_wallet}")
        return await process_valid_wallet(update, context)

    if text == "🔙 Назад":
        crypto_emoji = {'BTC': '🔸', 'LTC': '🔹', 'USDT': '💲'}[crypto]
        amount_with_bonus = Decimal(str(context.user_data['amount'])) - Decimal(
            str(context.user_data.get('bonus_to_use', 0)))
        cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
        cashback_percent = Decimal(str(cursor.fetchone()[0]))
        cashback_amount = amount_with_bonus * (cashback_percent / Decimal('100'))

        order_text = (
            f"📝 Детали обмена\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{crypto_emoji} Криптовалюта: {crypto}\n"
            f"💵 К получению: {context.user_data['crypto_amount']:.8f} {crypto}\n\n"
            f"💸 К оплате: {amount_with_bonus:,.0f} RUB\n"
            f"🎁 Кэшбэк: {float(cashback_percent)}% ({cashback_amount:,.0f} RUB)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🌟 Всё верно?"
        )
        await update.message.reply_text(
            order_text,
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Назад"), KeyboardButton("✅ Верно")]],
                                             resize_keyboard=True)
        )
        return CONFIRMING_DETAILS

    context.user_data['wallet'] = text
    await update.message.reply_text("⏳ Проверка кошелька...")

    if validate_wallet(text, crypto):
        save_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("💾 Сохранить адрес"), KeyboardButton("🚀 Продолжить без сохранения")],
            [KeyboardButton("🔙 Назад")]
        ], resize_keyboard=True)
        await update.message.reply_text("✅ Адрес валиден! Сохранить его?", reply_markup=save_keyboard)
        return CONFIRMING_DETAILS
    else:
        await update.message.reply_text("❌ Неверный адрес. Проверьте формат.")
        return ENTERING_WALLET


async def process_valid_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info("Вызвана функция process_valid_wallet")
    crypto = context.user_data['crypto']
    wallet = context.user_data['wallet']
    amount_with_bonus = Decimal(str(context.user_data['amount'])) - Decimal(
        str(context.user_data.get('bonus_to_use', 0)))
    amount_rub = "{:,.0f}".format(amount_with_bonus).replace(',', ' ')
    amount_crypto = "{:.8f}".format(context.user_data['crypto_amount']).rstrip('0').rstrip('.')
    cursor.execute('SELECT cashback_percent FROM settings WHERE id = 1')
    cashback_percent = Decimal(str(cursor.fetchone()[0]))
    cashback_amount = amount_with_bonus * (cashback_percent / Decimal('100'))
    crypto_emoji = {'BTC': '🔸', 'LTC': '🔹', 'USDT': '💲'}[crypto]

    order_text = (
        "📝 Заявка на обмен\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🏁 Адрес получения: `{wallet}`\n\n"
        f"{crypto_emoji} Криптовалюта: {crypto}\n"
        f"💵 К получению: {amount_crypto} {crypto}\n\n"
        f"💸 К оплате: {amount_rub} RUB\n"
        f"🎁 Кэшбэк: {float(cashback_percent)}% ({cashback_amount:,.0f} RUB)\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🌟 Создать заявку?"
    )

    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("❌ Отменить"), KeyboardButton("✅ Создать")]
    ], resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(order_text, reply_markup=keyboard, parse_mode='Markdown')
    logger.info("Сообщение с кнопками отправлено, возвращаем CONFIRMING_DETAILS")
    return CONFIRMING_DETAILS


async def check_order_expiration(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка истечения срока действия заявки"""
    job = context.job
    public_id = job.data['public_id']
    user_id = job.data['user_id']

    cursor.execute('SELECT status FROM orders WHERE public_id = ?', (public_id,))
    status = cursor.fetchone()[0]

    if status == 'pending':
        cursor.execute('UPDATE orders SET status = "expired" WHERE public_id = ?', (public_id,))
        conn.commit()
        logger.info(f"Заявка #{public_id} истекла")
        await context.bot.send_message(user_id, f"⏰ Заявка #{public_id} истекла и была удалена.")