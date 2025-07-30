import mysql.connector

def connect_to_database():
    return mysql.connector.connect(

        host="localhost",
        user="root",
        password="1310",
        database="magazzino_db"
    )