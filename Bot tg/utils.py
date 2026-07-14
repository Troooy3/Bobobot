#utils.py
import uuid
import requests
from decimal import Decimal
import re
from bech32 import bech32_decode

def generate_public_id():
    """Генерация уникального публичного ID."""
    return uuid.uuid4().hex[:12]

def get_crypto_rate(crypto: str) -> float:
    """Получение текущего курса криптовалюты в рублях."""
    try:
        response_usdt = requests.get(
            'https://api.binance.com/api/v3/ticker/price',
            params={'symbol': 'USDTRUB'},
            timeout=10
        )
        response_usdt.raise_for_status()
        usdt_rate = Decimal(response_usdt.json()['price'])

        if crypto == 'USDT':
            return float(usdt_rate)

        symbols = {'BTC': 'BTCUSDT', 'LTC': 'LTCUSDT'}
        response = requests.get(
            'https://api.binance.com/api/v3/ticker/price',
            params={'symbol': symbols[crypto]},
            timeout=10
        )
        response.raise_for_status()
        crypto_price = Decimal(response.json()['price'])

        return float(crypto_price * usdt_rate)
    except requests.RequestException as e:
        raise Exception(f"⚠️ Не удалось получить курс: {str(e)}")

def validate_wallet(address: str, crypto: str) -> bool:
    """Проверка валидности адреса кошелька"""
    patterns = {
        'BTC': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$',
        'LTC': r'^ltc1[a-z0-9]{39}$|^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$',
        'USDT': r'^(0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33})$'
    }
    
    if crypto not in patterns:
        return False
    
    pattern = re.compile(patterns[crypto])
    
    if crypto in ['BTC', 'LTC'] and address.startswith(('bc1', 'ltc1')):
        try:
            hrp, _ = bech32_decode(address)
            return hrp == 'bc' if crypto == 'BTC' else hrp == 'ltc'
        except Exception:
            return False
    
    return bool(pattern.match(address))

def get_example_address(crypto: str) -> str:
    """Получение примера адреса для криптовалюты."""
    examples = {
        'BTC': '1GUXVeT5fuMhCkneSuAaCMe6AZgnKkpkV8',
        'LTC': 'LcFFKBmB3LQk6xJdY8Zso4mJdYqDREBgVp',
        'USDT': (
            "TRC20: TYB1z8fAp3qZycXU1XnTTS5XGVhjJk8t7W\n"
        )
    }
    return examples.get(crypto, '')