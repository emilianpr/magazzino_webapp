import traceback
from app import app

app.config['PROPAGATE_EXCEPTIONS'] = True
app.debug = True

with app.test_client() as c:
    # Login
    c.post('/login', data={'username': 'Test', 'password': 'Test'})
    
    # Test tutte le pagine principali
    pages = ['/', '/statistiche', '/carico_merci', '/movimento', '/logmovimenti', '/rientro_merce']
    
    for page in pages:
        try:
            resp = c.get(page)
            if resp.status_code != 200:
                print(f'{page}: {resp.status_code}')
                print(resp.get_data(as_text=True)[:500])
            else:
                print(f'{page}: OK')
        except Exception as e:
            print(f'{page}: EXCEPTION')
            traceback.print_exc()
