from app import app
import json

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'test'
    
    # Test trend API
    print("=== TREND API ===")
    for range_val in ['30d', '6m', '1y']:
        resp = client.get(f'/api/statistiche/trend?range={range_val}')
        data = resp.get_json()
        if 'error' in data:
            print(f'{range_val}: ERROR - {data["error"]}')
        else:
            num_labels = len(data.get('labels', []))
            print(f'{range_val}: {num_labels} punti dati')
            print(f'  Labels: {data.get("labels", [])}')
    
    # Test main stats API
    print("\n=== MAIN STATS API ===")
    for range_val in ['30d', '6m', '1y']:
        resp = client.get(f'/api/statistiche?range={range_val}')
        data = resp.get_json()
        if 'error' in data:
            print(f'{range_val}: ERROR - {data["error"]}')
        else:
            kpi = data.get('kpi', {})
            print(f'{range_val}: totale_movimenti={kpi.get("totale_movimenti")}, carichi={kpi.get("totale_carichi")}, scarichi={kpi.get("totale_scarichi")}')
    
    # Test utenti API
    print("\n=== UTENTI API ===")
    for range_val in ['30d', '6m', '1y']:
        resp = client.get(f'/api/statistiche/utenti?range={range_val}')
        data = resp.get_json()
        if data.get('error'):
            print(f'{range_val}: ERROR - {data["error"]}')
        else:
            utenti = data.get('utenti', [])
            print(f'{range_val}: {len(utenti)} utenti')
    
    # Test top prodotti API
    print("\n=== TOP PRODOTTI API ===")
    for range_val in ['30d', '6m', '1y']:
        resp = client.get(f'/api/statistiche/top-prodotti?range={range_val}')
        data = resp.get_json()
        if data.get('error'):
            print(f'{range_val}: ERROR - {data["error"]}')
        else:
            prodotti = data.get('prodotti', [])
            print(f'{range_val}: {len(prodotti)} prodotti')
