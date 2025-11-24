import mysql.connector
from mysql.connector import pooling
import os

db_pool = None

def get_db_config():
    # Prova PRIMA config_local.py (priorità a file locale)
    try:
        from config_local import DATABASE_CONFIG
        return DATABASE_CONFIG
    except ImportError:
        pass  # Se config_local.py non esiste, usa variabili d'ambiente
    
    # Fallback a variabili d'ambiente
    db_password = os.getenv('DB_PASSWORD')
    if not db_password:
        raise Exception("Configurazione database non trovata. Crea config_local.py o imposta DB_PASSWORD")
    
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'user': os.getenv('DB_USER', 'magazzino_webapp'),
        'password': db_password,
        'database': os.getenv('DB_NAME', 'magazzino_db')
    }

def connect_to_database():
    global db_pool

    # Controlla se siamo in modalità manutenzione
    try:
        from app import MAINTENANCE_MODE
        if MAINTENANCE_MODE:
            raise Exception("Database non disponibile durante la manutenzione")
    except ImportError:
        pass  # Se non riesce a importare app, continua normalmente
    
    if db_pool is None:
        config = get_db_config()
        # Assicurati che autocommit sia False se non specificato, o gestiscilo come preferisci
        # mysql.connector default è autocommit=False
        db_pool = pooling.MySQLConnectionPool(
            pool_name="magazzino_pool",
            pool_size=10, # Aumentato a 10 per gestire meglio la concorrenza
            pool_reset_session=True,
            **config
        )
    
    return db_pool.get_connection()