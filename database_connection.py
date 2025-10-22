import mysql.connector

def connect_to_database():
    # Controlla se siamo in modalità manutenzione
    try:
        from app import MAINTENANCE_MODE
        if MAINTENANCE_MODE:
            raise Exception("Database non disponibile durante la manutenzione")
    except ImportError:
        pass  # Se non riesce a importare app, continua normalmente
    
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1312",
        database="magazzino_db"
    )