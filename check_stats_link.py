from app import app
import re

with app.test_client() as c:
    c.post('/login', data={'username': 'Test', 'password': 'Test'})
    
    resp = c.get('/')
    html = resp.get_data(as_text=True)
    
    # Cerca il link statistiche
    pattern = r'href="([^"]*statistiche[^"]*)"'
    matches = re.findall(pattern, html, re.IGNORECASE)
    print('Link statistiche trovati:')
    for m in matches:
        print(f'  {m}')
    
    # Cerca anche la stringa esatta del link
    if '/statistiche' in html:
        print('\n/statistiche è presente nel HTML')
    else:
        print('\n/statistiche NON è presente nel HTML')
