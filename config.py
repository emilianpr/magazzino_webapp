"""
Configurazione centralizzata per l'applicazione Flask.
Contiene tutte le costanti e configurazioni globali.
"""
import os

# ========================================
# APP VERSION
# ========================================
VERSION = "Beta v1.5"

# ========================================
# STATI DISPONIBILI (lista statica)
# ========================================
# Lista di tutti gli stati possibili per le giacenze
# Questa lista è statica per evitare che gli stati spariscano
# quando non ci sono più prodotti con quello stato
STATI_DISPONIBILI = [
    'IN_MAGAZZINO',
    'SPEDITO',
    'BAIA_USCITA',
    'IN_PREPARAZIONE',
    'IN_UTILIZZO',
    'LABORATORIO',
    'DANNEGGIATO',
    'ALTRO'
]

# ========================================
# MAINTENANCE MODE CONFIGURATION
# ========================================
MAINTENANCE_MODE = False

# Personalizza il messaggio dell'operazione in corso
MAINTENANCE_MESSAGE = "Aggiornamento alla Beta v1.4 - Tempo stimato: 1 ora"

# ========================================
# FLASK CONFIGURATION
# ========================================
class Config:
    """Configurazione base Flask"""
    
    # Compression settings
    COMPRESS_ALGORITHM = 'gzip'
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 1024
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/plain', 'application/json',
        'application/javascript', 'text/javascript', 'image/svg+xml'
    ]
    SEND_FILE_MAX_AGE_DEFAULT = 86400  # 1 day for static assets
    
    @staticmethod
    def init_app(app):
        """Inizializza l'app con la configurazione"""
        pass


class DevelopmentConfig(Config):
    """Configurazione per sviluppo"""
    DEBUG = True


class ProductionConfig(Config):
    """Configurazione per produzione"""
    DEBUG = False


# Mapping delle configurazioni
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def load_secret_key():
    """Carica la secret key dalla configurazione locale o variabile d'ambiente"""
    try:
        from config_local import FLASK_CONFIG
        return FLASK_CONFIG['secret_key']
    except ImportError:
        key = os.getenv('FLASK_SECRET_KEY', 'f3b1a67c9e8f4d2a85e37c1f9b7d4e6f2c1a5d8f9b3c4e7f0a1d2b3c4e5f6a7b')
        print("WARNING: Using default or environment SECRET_KEY. Create config_local.py for better security.")
        return key
