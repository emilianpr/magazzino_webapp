# Magazzino WebApp

Una webapp completa per gestire il magazzino della tua azienda, senza più fogli Excel disordinati o confusione su dove si trovano i prodotti. Nata per risolvere problemi reali di logistica quotidiana, permette di tracciare ogni movimento di merce, sapere sempre dove si trova ogni prodotto e riconciliare i dati con sistemi esterni come AS400.

## Cosa fa questa webapp?

Immagina di dover gestire centinaia di prodotti distribuiti in più magazzini, con ubicazioni specifiche (scaffali, baie, celle frigorifere). Questa webapp ti aiuta a:

- **Vedere subito dove si trova ogni cosa**: Dashboard con filtri intelligenti per trovare qualsiasi prodotto in pochi secondi, filtrando per codice, nome, ubicazione o stato.
- **Caricare nuova merce**: Quando arriva un prodotto, lo registri specificando quantità e dove lo metti fisicamente. Il sistema lo traccia automaticamente.
- **Scaricare merce quando serve**: Che si tratti di vendite, consumi interni o trasferimenti, puoi scaricare prodotti indicando da quale ubicazione precisa vengono prelevati.
- **Gestire stati speciali**: Non tutti i prodotti sono "in magazzino" - alcuni sono in baia d'uscita, altri in transito o in riparazione. La webapp tiene traccia anche di questi stati particolari.
- **Movimentare tra ubicazioni**: Sposti 50 unità dallo scaffale 10A al 15B? Registri il movimento e il sistema aggiorna automaticamente le giacenze.
- **Far rientrare merce**: Se hai prodotti fuori sede (in prestito, in riparazione, ecc.), puoi farli rientrare in modo guidato scegliendo dove riposizionarli.
- **Controllare tutto quello che succede**: Ogni operazione viene loggata con data, ora, utente e note. Nessun movimento si perde e puoi sempre risalire a chi ha fatto cosa.
- **Esportare report**: Genera file Excel o TXT con tutte le giacenze per verifiche periodiche o per l'ufficio amministrativo.
- **Riconciliare con AS400**: Se usi sistemi legacy AS400, puoi caricare i file di export e confrontarli automaticamente con i dati della webapp per trovare discrepanze.

## Caratteristiche tecniche
- Sistema di login con ruoli (utenti normali e amministratori)
- Dashboard responsive che funziona su PC, tablet e smartphone
- Dark mode AMOLED per lavorare anche di notte senza affaticare la vista
- API REST per integrazioni esterne o app mobile custom
- Modalità manutenzione per interventi sul database senza bloccare il servizio
- Installabile on-premise sul tuo server, nessun dato esce dalla tua rete

## Cosa ti serve per farla partire
- **Python 3.11+** (va bene anche 3.10, ma più recente è meglio)
- **MySQL 8** o MariaDB - il database dove vengono salvati tutti i dati
- Un **server Linux/macOS** o Windows con WSL per il deploy in produzione
- Tutto il resto viene installato automaticamente dai file di configurazione inclusi nel progetto

## Setup veloce per iniziare

1. **Scarica il progetto e prepara l'ambiente Python:**
   ```bash
   git clone <repo-url>
   cd magazzino_webapp
   python -m venv .venv
   source .venv/bin/activate  # su Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configura la connessione al database:**
   ```bash
   cp config_local.py.template config_local.py
   nano config_local.py  # o usa il tuo editor preferito
   ```
   Inserisci le credenziali del tuo database MySQL e genera una chiave segreta per Flask (c'è il comando nel file stesso).

3. **Prepara il database:**
   - Assicurati che MySQL sia avviato e raggiungibile
   - Importa lo schema del database (di solito fornito dal reparto IT o disponibile nei backup)
   - Il file contiene le tabelle per prodotti, giacenze, movimenti, utenti, log e changelog

4. **Verifica che sia tutto ok:**
   Il file `config_local.py` non deve MAI essere caricato su Git (è già escluso automaticamente) perché contiene password sensibili.

## Note sulla configurazione

Il cuore della configurazione sta nel file `config_local.py` dove metti le password del database e la chiave segreta di Flask. Se preferisci (o se lavori con Docker/Kubernetes), puoi anche usare le variabili d'ambiente `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` e `FLASK_SECRET_KEY`.

C'è anche una modalità manutenzione integrata: se devi fare interventi sul database o migrazioni, basta attivare il flag `MAINTENANCE_MODE` in `app.py` e tutti gli utenti vedranno una pagina di cortesia invece di ricevere errori strani. Per maggiori dettagli sulla configurazione, leggi il file `CONFIG_README.md`.

## Come avviarla

**In sviluppo locale:**
```bash
python app.py
```
La webapp si apre sulla porta 80 (quindi accessibile da `http://localhost`). Se la porta 80 è già occupata o preferisci usarne un'altra, modifica la riga finale di `app.py`.

**In produzione su server Debian/Ubuntu:**
Ci sono script già pronti per configurare tutto come servizio systemd:
- `start_port80.sh` - avvia manualmente la webapp
- `magazzino-port80.service` - file di configurazione per systemd (parte automaticamente al boot)
- `deploy_debian.sh` - script completo che instala dipendenze, configura permessi e attiva il servizio

In produzione è consigliato usare un reverse proxy (nginx o Apache) davanti a Flask per gestire SSL/HTTPS e migliorare le performance.

## Le pagine principali e cosa ci fai

**Login e gestione utenti:**
La prima cosa che vedi è la pagina di login. Solo gli amministratori possono registrare nuovi utenti, quindi il primo admin va creato manualmente nel database (o te lo crea chi ha fatto il setup iniziale).

**Dashboard (pagina principale):**
È il cuore dell'applicazione. Vedi tutte le giacenze con tanti filtri per trovare quello che cerchi: codice prodotto, nome, magazzino, ubicazione, stato. Puoi ordinare per qualsiasi colonna e modificare quantità al volo. Ogni modifica viene tracciata automaticamente.

**Carico merci:**
Quando arriva nuova merce, vai qui. Cerchi il prodotto (con autosuggest intelligente), dici quanti ne hai ricevuti, dove li metti e aggiungi eventuali note. Il sistema registra tutto e aggiorna le giacenze.

**Scarico merci:**
Due modalità: scarico dalla merce in magazzino (vendite, spedizioni) o scarico di merce in stati speciali (se è in riparazione, in baia d'uscita, ecc.). Selezioni il prodotto, l'ubicazione se serve, e la quantità. Fine.

**Rientro merce:**
Hai mandato qualcosa in prestito o in riparazione? Quando torna, usi questa pagina per farla rientrare in magazzino. Scegli dove riposizionarla e il sistema aggiorna tutto.

**Movimenti:**
La pagina "esperto" per chi deve fare operazioni complesse: spostare merce da un magazzino all'altro, cambiare stato, trasferire tra ubicazioni. Hai il controllo totale su origine e destinazione.

**Log e report:**
Due sezioni separate per vedere lo storico completo: tutti i movimenti (trasferimenti, carichi) e tutti gli scarichi. Puoi anche esportare tutto in Excel o in file di testo formattato per l'amministrazione.

**Riconciliazione magazzino:**
Se usi AS400 o altri sistemi legacy, puoi caricare i loro file di export e confrontarli con i dati della webapp. Il sistema ti dice dove ci sono differenze, cosa manca e cosa c'è in più. Perfetto per le verifiche di fine mese.

## API per integrazioni

Se vuoi creare un'app mobile custom o integrare la webapp con altri sistemi, ci sono diverse API REST disponibili:

- **`GET /api/health`** - Controlla se l'applicazione è attiva (utile per monitoring)
- **`GET /api/ubicazioni/<prodotto_id>`** - Ottieni tutte le ubicazioni dove si trova un prodotto
- **`GET /api/ubicazioni_per_prodotto/<prodotto_id>`** - Ubicazioni disponibili in magazzino per quel prodotto
- **`GET /api/quantita_disponibile/<prodotto_id>?ubicazione=...`** - Quante unità sono disponibili in totale o per ubicazione specifica
- **`POST /api/debug-as400-format`** - Tool di debug per verificare il formato dei file AS400 durante la riconciliazione

Tutte le API restituiscono JSON e richiedono autenticazione tramite sessione.

## Script utili inclusi

- **`deploy_debian.sh`** - Script automatico per installare tutto su un server Debian/Ubuntu pulito. Installa dipendenze, configura servizi, sistema i permessi. Molto comodo per il deploy iniziale.

- **`generate-passwordhash.py`** - Tool per creare hash di password da inserire manualmente nel database (per esempio per il primo admin).

- **`update_dark_mode.py`** - Script per aggiornare il tema dark mode AMOLED su tutti i template. L'interfaccia usa Tailwind CSS e Alpine.js per essere responsive e veloce.

- **`fix_try_blocks.py` e `fix-gap.*`** - Script di manutenzione per fix rapidi su codice legacy o regressioni specifiche.

## Struttura cartelle essenziali
```
app.py                     # Applicazione Flask con tutte le route
config_local.py.template   # Template per credenziali locali
static/                    # CSS/JS personalizzati (dark mode, fix UI)
templates/                 # Pagine Jinja (dashboard, carico, log, ecc.)
magazzino_reconciliation.py# Logica di confronto export vs AS400
database_connection.py     # Factory di connessioni MySQL
CONFIG_README.md           # Guida dettagliata alla configurazione
```

## Problemi comuni e soluzioni

**"Non riesco a collegarmi al database"**
Controlla che MySQL sia attivo, che le credenziali in `config_local.py` siano corrette e che l'utente del database abbia i permessi necessari (SELECT, INSERT, UPDATE, DELETE sulle tabelle).

**"La webapp si avvia ma mi butta fuori dopo il login"**
Probabilmente manca la `secret_key` in `config_local.py`. Generane una con questo comando:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
e aggiungila nella configurazione Flask.

**"Non vedo le modifiche CSS/JS che ho fatto"**
Il browser sta usando la cache. Premi Ctrl+F5 per ricaricare forzatamente la pagina, oppure apri gli strumenti sviluppatore e disabilita la cache mentre sviluppi.

**"Non riesco a registrare nuovi utenti"**
La pagina di registrazione è visibile solo agli amministratori. Il primo admin va creato manualmente nel database, impostando il campo `is_admin = 1` nella tabella `utenti`.

**"Tutti vedono la pagina di manutenzione"**
Hai lasciato attivo il flag `MAINTENANCE_MODE = True` in `app.py`. Cambialo a `False` e riavvia la webapp.

## Vuoi contribuire?

Il progetto è in continua evoluzione e ogni aiuto è benvenuto:

1. **Hai trovato un bug?** Apri una issue su GitHub descrivendo il problema e come riprodurlo.
2. **Hai un'idea per migliorare qualcosa?** Prima apri una issue per discuterne, poi fai una pull request con le modifiche.
3. **Modifichi il database?** Documenta sempre cosa cambia nello schema e fornisci script di migrazione.
4. **Modifichi l'interfaccia?** Aggiungi screenshot nella pull request così si capisce subito cosa cambia.

---

**Riferimenti utili:**
- `CONFIG_README.md` - Tutto sulla configurazione sicura del database e delle credenziali
- `app.py` - Il codice principale con tutte le route e la logica di business
- `.github/instructions/copilot-instructions.md` - Linee guida per sviluppatori e convenzioni del progetto

Per qualsiasi dubbio, apri una issue o contatta il team di sviluppo! 🚀
