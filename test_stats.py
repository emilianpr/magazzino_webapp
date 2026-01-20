import traceback
import sys

from app import app

app.config['TESTING'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['TRAP_HTTP_EXCEPTIONS'] = True
app.debug = True

with app.test_client() as c:
    # Login
    c.post('/login', data={'username': 'Test', 'password': 'Test'})
    
    # Accedi a statistiche
    try:
        resp = c.get('/statistiche')
        print('Status:', resp.status_code)
    except Exception as e:
        print('EXCEPTION:')
        traceback.print_exc()
