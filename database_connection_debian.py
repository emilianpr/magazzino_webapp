import mysql.connector
import os

def connect_to_database():
    # Check maintenance mode
    try:
        from app import MAINTENANCE_MODE
        if MAINTENANCE_MODE:
            raise Exception("Database not available during maintenance")
    except ImportError:
        pass
    
    # Use environment variables for production
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'magazzino_user'),
        password=os.getenv('DB_PASSWORD', 'your_password'),
        database=os.getenv('DB_NAME', 'magazzino_db')
    )
