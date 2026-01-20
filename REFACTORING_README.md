# Struttura Moduli Refactoring

Questo documento descrive la nuova struttura modulare creata per organizzare meglio il codice dell'applicazione Flask.

## Struttura Cartelle

```
magazzino_webapp/
├── app.py                  # File principale (ridotto dopo refactoring)
├── config.py               # Configurazione centralizzata
├── database_connection.py  # Connessione al database
├── routes/                 # Blueprint Flask - routes modulari
│   ├── __init__.py
│   ├── auth.py            # Autenticazione (login, logout, register)
│   ├── admin.py           # Pannello admin (/admin/*)
│   └── statistics.py      # Statistiche (/statistiche, /api/statistiche/*)
├── utils/                  # Utilities e helpers
│   ├── __init__.py
│   ├── decorators.py      # Decorators per autenticazione
│   └── cache.py           # Sistema di caching statistiche
├── templates/              # Template HTML
└── static/                 # File statici (CSS, JS)
```

## Moduli Creati

### config.py
Contiene:
- `VERSION` - Versione dell'app
- `STATI_DISPONIBILI` - Lista stati giacenze
- `MAINTENANCE_MODE` - Flag manutenzione
- `Config`, `DevelopmentConfig`, `ProductionConfig` - Classi configurazione Flask

### utils/decorators.py
Decorators per autenticazione:
- `@login_required` - Richiede utente loggato (redirect a login)
- `@admin_required` - Richiede admin (abort 403)
- `@api_login_required` - Per API, ritorna JSON 401
- `@api_admin_required` - Per API admin, ritorna JSON 403

### utils/cache.py
Sistema caching statistiche:
- `STATS_CACHE` - Dizionario cache in memoria
- `CACHE_TTL` - Tempo di vita cache (300 secondi)
- `get_stats_cache_key()` - Genera chiave cache
- `get_cached_stats()` - Recupera da cache
- `set_cached_stats()` - Salva in cache
- `clear_stats_cache()` - Svuota cache

### routes/auth.py (auth_bp)
Routes autenticazione:
- `GET/POST /login` - Login utente
- `GET /logout` - Logout utente
- `GET/POST /register` - Registrazione nuovi utenti

### routes/admin.py (admin_bp)
Routes pannello admin (url_prefix='/admin'):
- `GET /admin/` - Pannello principale
- `GET/POST /admin/users` - Gestione utenti
- `POST /admin/broadcast` - Notifiche broadcast

### routes/statistics.py (stats_bp)
Routes statistiche:
- `GET /statistiche` - Pagina statistiche
- `GET /api/statistiche` - API KPI principali
- `GET /api/statistiche/trend` - API dati grafico trend
- `GET /api/statistiche/per-stato` - API distribuzione per stato
- `GET /api/statistiche/utenti` - API breakdown utenti
- `GET /api/statistiche/top-prodotti` - API prodotti più movimentati
- `GET /api/statistiche/export/csv` - Export CSV
- `GET /api/statistiche/export/pdf` - Export PDF con grafici

## Come Completare il Refactoring

### Fase 1 - Testare i Blueprint (CORRENTE)
1. Decommentare gli import in app.py (riga ~17-19)
2. Decommentare le registrazioni blueprint (riga ~60-62)
3. Testare che l'app funzioni correttamente

### Fase 2 - Rimuovere Duplicati
Dopo aver verificato che i blueprint funzionano:
1. Rimuovere le routes duplicate da app.py
2. Rimuovere le funzioni helper duplicate
3. Testare nuovamente

### Fase 3 - Continuare l'Estrazione
Creare ulteriori blueprint per:
- `routes/products.py` - Gestione prodotti
- `routes/movements.py` - Movimenti (carico, scarico, trasferimento)
- `routes/inventory.py` - Giacenze e ubicazioni
- `routes/thresholds.py` - Soglie e notifiche
- `routes/warehouses.py` - Gestione magazzini
- `routes/reconciliation.py` - Riconciliazione AS400

## Note Importanti

1. **Compatibilità**: I blueprint sono pronti ma commentati per evitare conflitti
2. **Database**: Tutti i moduli usano `database_connection.py` per le connessioni
3. **Autenticazione**: I decorators in `utils/decorators.py` sono indipendenti
4. **Cache**: Il sistema cache in `utils/cache.py` è condiviso tra moduli
