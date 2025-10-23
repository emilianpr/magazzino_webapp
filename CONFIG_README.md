# Configurazione Database - Setup

## 🔐 Configurazione Sicura

Le password e le chiavi segrete **NON** sono nel codice. Ogni ambiente ha il proprio file di configurazione locale.

## 📋 Setup Iniziale

1. **Copia il template**:
   ```bash
   cp config_local.py.template config_local.py
   ```

2. **Modifica le credenziali**:
   ```bash
   nano config_local.py  # o usa il tuo editor preferito
   ```

3. **Inserisci i tuoi dati**:
   - Password del database
   - Secret key di Flask (genera con: `python -c "import secrets; print(secrets.token_hex(32))"`)

4. **NON commitare `config_local.py`**:
   - Il file è già in `.gitignore`
   - Contiene le tue password private
   - Ogni sviluppatore/server ha il proprio

## 🖥️ Ambienti Diversi

### Sviluppo (Windows/Mac/Linux)
```python
FLASK_CONFIG = {
    'debug': True  # Mostra errori dettagliati
}
```

### Produzione (Server)
```python
FLASK_CONFIG = {
    'debug': False  # Nasconde errori agli utenti
}
```

## ✅ Sicurezza

- ✅ Password in file locale non tracciato
- ✅ File escluso da Git (`.gitignore`)
- ✅ Ogni ambiente ha credenziali diverse
- ✅ Secret key unica per ogni installazione

## 🔍 Verifica

Controlla che `config_local.py` non sia tracciato:
```bash
git status
# Non deve apparire config_local.py nella lista
```
