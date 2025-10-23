import mysql.connector
import os

def connect_to_database():
    # Controlla se siamo in modalità manutenzione
    try:
        from app import MAINTENANCE_MODE
        if MAINTENANCE_MODE:
            raise Exception("Database non disponibile durante la manutenzione")
    except ImportError:
        pass  # Se non riesce a importare app, continua normalmente
    
    # Prova PRIMA config_local.py (priorità a file locale)
    try:
        from config_local import DATABASE_CONFIG
        return mysql.connector.connect(**DATABASE_CONFIG)
    except ImportError:
        pass  # Se config_local.py non esiste, usa variabili d'ambiente
    
    # Fallback a variabili d'ambiente
    db_password = os.getenv('DB_PASSWORD')
    if not db_password:
        raise Exception("Configurazione database non trovata. Crea config_local.py o imposta DB_PASSWORD")
    
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'magazzino_webapp'),
        password=db_password,
        database=os.getenv('DB_NAME', 'magazzino_db')
    )