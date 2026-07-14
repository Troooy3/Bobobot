import requests
import time
import config

# Кеш курса
_cached_rate = None
_cache_time = 0

def get_crypto_rate(crypto: str) -> float:
    """
    Получает курс криптовалюты к RUB с кешированием на CACHE_TIMEOUT секунд.
    При ошибке повторяет до 3 раз.
    """
    global _cached_rate, _cache_time
    
    now = time.time()
    if _cached_rate is not None and (now - _cache_time) < config.CACHE_TIMEOUT:
        return _cached_rate
    
    # Маппинг символов для Binance
    symbol_map = {
        "BTC": "BTCRUB",
        "LTC": "LTCRUB",
        "USDT": "USDTTRY"  # Для USDT используем пару к TRY (можно заменить)
    }
    symbol = symbol_map.get(crypto.upper())
    if not symbol:
        raise ValueError(f"Неподдерживаемая криптовалюта: {crypto}")
    
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            rate = float(data["price"])
            _cached_rate = rate
            _cache_time = now
            return rate
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Не удалось получить курс {crypto}: {e}")
            time.sleep(1)
