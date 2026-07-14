import sqlite3
import config

def get_db_connection():
    """Возвращает соединение с БД (с отключением проверки потоков)"""
    conn = sqlite3.connect(config.DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация таблиц и создание настроек по умолчанию"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            referrer_id INTEGER,
            referral_count INTEGER DEFAULT 0,
            cashback_earned REAL DEFAULT 0
        )
    ''')
    
    # Таблица заявок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            crypto_type TEXT,
            amount_rub REAL,
            amount_crypto REAL,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            bonus REAL DEFAULT 0
        )
    ''')
    
    # Таблица настроек (одна строка с id=1)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id=1),
            markup_percent REAL DEFAULT 5.0,
            cashback_percent REAL DEFAULT 2.0,
            referral_percent REAL DEFAULT 5.0,
            min_btc REAL DEFAULT 0.001,
            max_btc REAL DEFAULT 1.0,
            min_ltc REAL DEFAULT 0.1,
            max_ltc REAL DEFAULT 10.0,
            min_usdt REAL DEFAULT 10.0,
            max_usdt REAL DEFAULT 1000.0,
            order_timeout_minutes INTEGER DEFAULT 30
        )
    ''')
    
    # Если нет записи с id=1, создаём с настройками по умолчанию
    cursor.execute("SELECT COUNT(*) FROM settings WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id) VALUES (1)
        ''')
    
    conn.commit()
    conn.close()
