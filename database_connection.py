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
        print("🔧 DEBUG: Usando config_local.py")
        print(f"   DB_USER: {DATABASE_CONFIG.get('user')}")
        print(f"   DB_HOST: {DATABASE_CONFIG.get('host')}")
        print(f"   DB_NAME: {DATABASE_CONFIG.get('database')}")
        print(f"   Password length: {len(DATABASE_CONFIG.get('password', ''))} caratteri")
        return mysql.connector.connect(**DATABASE_CONFIG)
    except ImportError:
        pass  # Se config_local.py non esiste, usa variabili d'ambiente
    
    # Fallback a variabili d'ambiente
    db_password = os.getenv('DB_PASSWORD')
    if not db_password:
        raise Exception("Configurazione database non trovata. Crea config_local.py o imposta DB_PASSWORD")
    
    print("🔧 DEBUG: Usando variabili d'ambiente")
    print(f"   DB_USER: {os.getenv('DB_USER', 'magazzino_webapp')}")
    print(f"   DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
    print(f"   DB_NAME: {os.getenv('DB_NAME', 'magazzino_db')}")
    
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'magazzino_webapp'),
        password=db_password,
        database=os.getenv('DB_NAME', 'magazzino_db')
    )