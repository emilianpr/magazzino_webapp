from database_connection import connect_to_database

conn = connect_to_database()
cursor = conn.cursor(dictionary=True)

# Trova una giacenza per test
cursor.execute("SELECT g.id, g.prodotto_id, g.quantita, p.nome_prodotto FROM giacenze g JOIN prodotti p ON g.prodotto_id = p.id WHERE g.stato = 'IN_MAGAZZINO' LIMIT 5")
giacenze = cursor.fetchall()

print('Giacenze IN_MAGAZZINO:')
for g in giacenze:
    print(f"  ID: {g['id']}, Prodotto: {g['nome_prodotto']}, Qtà: {g['quantita']}")
    # Cerca altre giacenze dello stesso prodotto
    cursor.execute("SELECT id, ubicazione, quantita FROM giacenze WHERE prodotto_id = %s AND id != %s AND stato = 'IN_MAGAZZINO' AND quantita > 0", (g['prodotto_id'], g['id']))
    altre = cursor.fetchall()
    if altre:
        print(f"    Altre giacenze disponibili: {altre}")
    else:
        print(f"    NESSUNA altra giacenza disponibile!")

cursor.close()
conn.close()
