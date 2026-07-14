import sqlite3
import os
import logging

logger = logging.getLogger('CryptoBotDB')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('🎮 %(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

conn = sqlite3.connect('crypto_bot.db', check_same_thread=False)
cursor = conn.cursor()

def check_table_columns(table_name, required_columns):
    """Проверка наличия всех необходимых колонок в таблице"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = [col[1] for col in cursor.fetchall()]
    for col_name, col_def in required_columns.items():
        if col_name not in existing_columns:
            logger.warning(f"Колонка {col_name} отсутствует в таблице {table_name}, добавляем...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_def}")
            conn.commit()
            logger.info(f"Колонка {col_name} добавлена в таблицу {table_name}")

def init_db():
    """Инициализация таблиц базы данных"""
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                markup_percent REAL DEFAULT 5.0,
                cashback_percent REAL DEFAULT 2.0,
                referral_percent REAL DEFAULT 50.0,
                min_amount_btc REAL DEFAULT 1000.0,
                min_amount_ltc REAL DEFAULT 1000.0,
                min_amount_usdt REAL DEFAULT 1000.0,
                max_amount_btc REAL DEFAULT 1000000.0,
                max_amount_ltc REAL DEFAULT 1000000.0,
                max_amount_usdt REAL DEFAULT 1000000.0,
                expiration_timeout INTEGER DEFAULT 15
            )
        ''')
        settings_columns = {
            'id': 'INTEGER PRIMARY KEY',
            'markup_percent': 'REAL DEFAULT 5.0',
            'cashback_percent': 'REAL DEFAULT 2.0',
            'referral_percent': 'REAL DEFAULT 50.0',
            'min_amount_btc': 'REAL DEFAULT 1000.0',
            'min_amount_ltc': 'REAL DEFAULT 1000.0',
            'min_amount_usdt': 'REAL DEFAULT 1000.0',
            'max_amount_btc': 'REAL DEFAULT 1000000.0',
            'max_amount_ltc': 'REAL DEFAULT 1000000.0',
            'max_amount_usdt': 'REAL DEFAULT 1000000.0',
            'expiration_timeout': 'INTEGER DEFAULT 15'
        }
        check_table_columns('settings', settings_columns)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                referrer_id INTEGER,
                balance REAL DEFAULT 0.0,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                wallet_address TEXT
            )
        ''')
        users_columns = {
            'user_id': 'INTEGER PRIMARY KEY',
            'username': 'TEXT',
            'referrer_id': 'INTEGER',
            'balance': 'REAL DEFAULT 0.0',
            'registration_date': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
            'wallet_address': 'TEXT'
        }
        check_table_columns('users', users_columns)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT NOT NULL UNIQUE,
                user_id INTEGER,
                crypto TEXT,
                amount REAL,
                crypto_amount REAL,
                rate REAL,
                markup REAL,
                status TEXT DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                expiration_time DATETIME,
                processed_time DATETIME,
                wallet_address TEXT,
                bonus_used REAL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        orders_columns = {
            'order_id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'public_id': 'TEXT NOT NULL UNIQUE',
            'user_id': 'INTEGER',
            'crypto': 'TEXT',
            'amount': 'REAL',
            'crypto_amount': 'REAL',
            'rate': 'REAL',
            'markup': 'REAL',
            'status': 'TEXT DEFAULT "pending"',
            'timestamp': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
            'expiration_time': 'DATETIME',
            'processed_time': 'DATETIME',
            'wallet_address': 'TEXT',
            'bonus_used': 'REAL DEFAULT 0'
        }
        check_table_columns('orders', orders_columns)

        cursor.execute('INSERT OR IGNORE INTO settings (id) VALUES (1)')
        conn.commit()
        logger.info("База данных успешно инициализирована")

    except sqlite3.Error as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise
    except Exception as e:
        logger.error(f"Неизвестная ошибка при инициализации базы данных: {e}")
        raise

init_db()