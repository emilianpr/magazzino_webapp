"""
Sistema di cache per le statistiche.
Evita query pesanti ripetute memorizzando i risultati.
"""
import time

# Cache per le statistiche - evita query pesanti ripetute
STATS_CACHE = {}
CACHE_TTL = 300  # 5 minuti in secondi


def get_stats_cache_key(prefix, range_param, user_id=None):
    """Genera una chiave di cache per le statistiche"""
    key = f"{prefix}_{range_param}"
    if user_id:
        key += f"_{user_id}"
    return key


def get_cached_stats(key):
    """Recupera statistiche dalla cache se valide"""
    if key in STATS_CACHE:
        cached = STATS_CACHE[key]
        if time.time() - cached['timestamp'] < CACHE_TTL:
            return cached['data']
    return None


def set_cached_stats(key, data):
    """Salva statistiche in cache"""
    STATS_CACHE[key] = {
        'data': data,
        'timestamp': time.time()
    }


def clear_stats_cache():
    """Svuota la cache delle statistiche"""
    global STATS_CACHE
    STATS_CACHE = {}
