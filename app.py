from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_compress import Compress
import mysql.connector
from mysql.connector import Error
from database_connection import connect_to_database
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_file, make_response
from datetime import datetime
import io
import tempfile
import os
import xlsxwriter
from magazzino_reconciliation import process_uploaded_files, get_webapp_api_response
import logging

# ========================================
# IMPORT BLUEPRINTS MODULARI
# ========================================
# I blueprints separano le routes in moduli per migliorare la manutenibilità
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.statistics import stats_bp

# Filtro per escludere le richieste di polling dalle log
class NotificationLogFilter(logging.Filter):
    """Filtra i log delle richieste di polling notifiche per evitare spam nei log."""
    def filter(self, record):
        message = record.getMessage()
        # Escludi richieste GET a /notifications
        if 'GET /notifications' in message:
            return False
        return True

# Applica il filtro al logger di Werkzeug
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(NotificationLogFilter())


app = Flask(__name__)

# Performance: enable gzip compression and static caching
app.config.setdefault('COMPRESS_ALGORITHM', 'gzip')
app.config.setdefault('COMPRESS_LEVEL', 6)
app.config.setdefault('COMPRESS_MIN_SIZE', 1024)
app.config.setdefault('COMPRESS_MIMETYPES', [
    'text/html', 'text/css', 'text/plain', 'application/json',
    'application/javascript', 'text/javascript', 'image/svg+xml'
])
app.config.setdefault('SEND_FILE_MAX_AGE_DEFAULT', 86400)  # 1 day for static assets
Compress(app)

# Carica la configurazione Flask da config_local.py o variabile d'ambiente
try:
    from config_local import FLASK_CONFIG
    app.secret_key = FLASK_CONFIG['secret_key']
    app.config['DEBUG'] = FLASK_CONFIG.get('debug', False)
except ImportError:
    # Fallback a variabile d'ambiente
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'f3b1a67c9e8f4d2a85e37c1f9b7d4e6f2c1a5d8f9b3c4e7f0a1d2b3c4e5f6a7b')
    print("WARNING: Using default or environment SECRET_KEY. Create config_local.py for better security.")

# ========================================
# REGISTRAZIONE BLUEPRINTS
# ========================================
app.register_blueprint(auth_bp)                    # /login, /logout, /register
app.register_blueprint(admin_bp, url_prefix='/admin')  # /admin/*
app.register_blueprint(stats_bp)                   # /statistiche, /api/statistiche/*

# ========================================
# APP VERSION
# ========================================
VERSION = "Beta v1.5.2"

# ========================================
# STATI DISPONIBILI (lista statica)
# ========================================
# Lista di tutti gli stati possibili per le giacenze
# Questa lista è statica per evitare che gli stati spariscano
# quando non ci sono più prodotti con quello stato
STATI_DISPONIBILI = [
    'IN_MAGAZZINO',
    'SPEDITO',
    'BAIA_USCITA',
    'IN_PREPARAZIONE',
    'IN_UTILIZZO',
    'LABORATORIO',
    'DANNEGGIATO',
    'ALTRO'
]

# ========================================
# MAINTENANCE MODE CONFIGURATION
# ========================================
MAINTENANCE_MODE = False

# Personalizza il messaggio dell'operazione in corso
# Cambia questo testo per descrivere l'operazione specifica
MAINTENANCE_MESSAGE = "Aggiornamento alla Beta v1.4 - Tempo stimato: 1 ora"

# ========================================
# STATISTICS CACHE SYSTEM
# ========================================
import time
from functools import wraps

# Cache per le statistiche - evita query pesanti ripetute
STATS_CACHE = {}
CACHE_TTL = 300  # 5 minuti in secondi

def get_stats_cache_key(prefix, range_param, user_id=None):
    """Genera una chiave di cache per le statistiche"""
    key = f"{prefix}_{range_param}"
    if user_id:
        key += f"_{user_id}"
    return key

def get_cached_stats(key):
    """Recupera statistiche dalla cache se valide"""
    if key in STATS_CACHE:
        cached = STATS_CACHE[key]
        if time.time() - cached['timestamp'] < CACHE_TTL:
            return cached['data']
    return None

def set_cached_stats(key, data):
    """Salva statistiche in cache"""
    STATS_CACHE[key] = {
        'data': data,
        'timestamp': time.time()
    }

def clear_stats_cache():
    """Svuota la cache delle statistiche"""
    global STATS_CACHE
    STATS_CACHE = {}

# Before request handler per controllare la manutenzione
@app.before_request
def check_maintenance():
    if MAINTENANCE_MODE:
        # Permetti l'accesso alla pagina di manutenzione stessa
        if request.endpoint != 'maintenance' and request.endpoint != 'static':
            return redirect(url_for('maintenance'))

# Route per la pagina di manutenzione
@app.route('/maintenance')
def maintenance():
    # Se la maintenance mode non è attiva, reindirizza a index
    if not MAINTENANCE_MODE:
        return redirect(url_for('index'))
    return render_template('maintenance.html', maintenance_message=MAINTENANCE_MESSAGE)

# API: ubicazioni disponibili per prodotto (per scaricomerce)
@app.route('/api/ubicazioni_per_prodotto/<int:prodotto_id>')
def api_ubicazioni_per_prodotto(prodotto_id):
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT ubicazione FROM giacenze
            WHERE prodotto_id = %s AND stato = 'in_magazzino' AND ubicazione IS NOT NULL AND ubicazione != '' AND quantita > 0
        """, (prodotto_id,))
        ubicazioni = [row['ubicazione'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(ubicazioni)
    except Exception as e:
        return jsonify([]), 500



# API: quantità disponibile per prodotto (totale o per ubicazione)
@app.route('/api/quantita_disponibile/<int:prodotto_id>')
def api_quantita_disponibile(prodotto_id):
    try:
        ubicazione = request.args.get('ubicazione')
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        if ubicazione is not None:
            if ubicazione == '':
                # tutte le ubicazioni
                cursor.execute("""
                    SELECT SUM(quantita) AS quantita
                    FROM giacenze
                    WHERE prodotto_id = %s AND stato = 'in_magazzino'
                """, (prodotto_id,))
            else:
                cursor.execute("""
                    SELECT SUM(quantita) AS quantita
                    FROM giacenze
                    WHERE prodotto_id = %s AND stato = 'in_magazzino' AND ubicazione = %s
                """, (prodotto_id, ubicazione))
        else:
            cursor.execute("""
                SELECT SUM(quantita) AS quantita
                FROM giacenze
                WHERE prodotto_id = %s AND stato = 'in_magazzino'
            """, (prodotto_id,))
        
        row = cursor.fetchone()
        quantita = int(row['quantita']) if row and row['quantita'] is not None else 0
        cursor.close()
        conn.close()
        return jsonify({'quantita': quantita})
    except Exception as e:
        return jsonify({'quantita': 0, 'error': str(e)}), 500

@app.context_processor
def inject_user():
    return dict(username=session.get('username'))

# Jinja2 filter to format database strings
def format_db_string(value):
    if not value:
        return ''
    # Replace underscores with spaces and capitalize each word
    return ' '.join(word.capitalize() for word in value.replace('_', ' ').split())

app.jinja_env.filters['format_db_string'] = format_db_string

# Context processor: versione applicazione (usa la variabile VERSION)
@app.context_processor
def inject_app_version():
    return dict(app_version=VERSION)

# API endpoint to get ubicazioni with quantities for a given prodotto_id
@app.route("/api/ubicazioni_prodotto/<int:prodotto_id>")
def api_ubicazioni_prodotto(prodotto_id):
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ubicazione, SUM(quantita) as quantita
            FROM giacenze 
            WHERE prodotto_id = %s AND stato = 'in_magazzino' AND ubicazione IS NOT NULL AND ubicazione != ''
            GROUP BY ubicazione
            HAVING SUM(quantita) > 0
            ORDER BY ubicazione
        """, (prodotto_id,))
        ubicazioni = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'ubicazioni': ubicazioni})
    except Exception as e:
        return jsonify({'ubicazioni': [], 'error': str(e)}), 500

# API endpoint to get ubicazioni for a given prodotto_id
@app.route("/api/ubicazioni/<int:prodotto_id>")
def api_ubicazioni(prodotto_id):
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT ubicazione FROM giacenze WHERE prodotto_id = %s AND ubicazione IS NOT NULL AND ubicazione != ''
        """, (prodotto_id,))
        ubicazioni = [row['ubicazione'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(ubicazioni)
    except Error as e:
        return jsonify([]), 500

# Home Page: visualizza giacenze con filtri e ordinamento
@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    filtro_codice = request.args.get('filtro_codice', '').strip()
    filtro_nome = request.args.get('filtro_nome', '').strip()
    filtro_magazzino = request.args.get('filtro_magazzino', '').strip()
    filtro_stato = request.args.get('filtro_stato', '').strip()
    filtro_ubicazione = request.args.get('filtro_ubicazione', '').strip()
    filtro_note = request.args.get('filtro_note', '').strip()
    ordine = request.args.get('ordine', 'codice_prodotto_asc')

    ordini_possibili = {
        'codice_prodotto_asc': 'p.codice_prodotto ASC',
        'codice_prodotto_desc': 'p.codice_prodotto DESC',
        'nome_prodotto_asc': 'p.nome_prodotto ASC',
        'nome_prodotto_desc': 'p.nome_prodotto DESC',
        'magazzino_asc': 'm.nome ASC',
        'magazzino_desc': 'm.nome DESC',
        'stato_asc': 'g.stato ASC',
        'stato_desc': 'g.stato DESC',
        'ubicazione_asc': 'g.ubicazione ASC',
        'ubicazione_desc': 'g.ubicazione DESC',
        'quantita_asc': 'g.quantita ASC',
        'quantita_desc': 'g.quantita DESC',
    }
    order_by = ordini_possibili.get(ordine, 'p.codice_prodotto ASC')

    cursor = None
    conn = None
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)

        # Query per giacenze con filtri, including latest movement note
        query = """
            SELECT g.id, p.codice_prodotto, p.nome_prodotto, m.nome AS magazzino, g.ubicazione, g.stato, g.quantita, g.note,
                   (SELECT note FROM movimenti mv WHERE mv.prodotto_id = g.prodotto_id ORDER BY mv.data_ora DESC LIMIT 1) AS latest_movement_note
            FROM giacenze g
            JOIN prodotti p ON g.prodotto_id = p.id
            JOIN magazzini m ON g.magazzino_id = m.id
            WHERE 1=1
        """
        params = []

        if filtro_codice:
            query += " AND p.codice_prodotto LIKE %s"
            params.append(f"%{filtro_codice}%")
        if filtro_nome:
            query += " AND p.nome_prodotto LIKE %s"
            params.append(f"%{filtro_nome}%")
        if filtro_magazzino:
            query += " AND m.nome LIKE %s"
            params.append(f"%{filtro_magazzino}%")
        if filtro_stato:
            query += " AND TRIM(UPPER(g.stato)) = TRIM(UPPER(%s))"
            params.append(filtro_stato)
        if filtro_ubicazione:
            query += " AND g.ubicazione LIKE %s"
            params.append(f"%{filtro_ubicazione}%")
        if filtro_note:
            # Cerca solo nelle note della giacenza corrente, non nei movimenti
            query += " AND g.note LIKE %s"
            params.append(f"%{filtro_note}%")

        query += f" ORDER BY {order_by}"

        cursor.execute(query, params)
        giacenze = cursor.fetchall()
        
        # Debug: mostra info filtro nella pagina
        if filtro_stato and len(giacenze) == 0:
            # Controlla quante giacenze hanno quello stato nel DB
            cursor.execute("SELECT COUNT(*) as cnt FROM giacenze WHERE TRIM(UPPER(stato)) = TRIM(UPPER(%s))", (filtro_stato,))
            count_stato = cursor.fetchone()['cnt']
            flash(f"DEBUG: Filtro '{filtro_stato}' - Trovate {count_stato} giacenze con questo stato nel DB, ma 0 dopo filtri combinati", "info")

        # Query per opzioni filtro magazzino, stato e ubicazione
        cursor.execute("SELECT DISTINCT nome FROM magazzini ORDER BY nome ASC")
        magazzini_opzioni = [row['nome'] for row in cursor.fetchall()]

        # Usa la lista statica degli stati invece di SELECT DISTINCT
        stati_opzioni = STATI_DISPONIBILI.copy()

        cursor.execute("SELECT DISTINCT ubicazione FROM giacenze ORDER BY ubicazione ASC")
        ubicazioni_opzioni = [row['ubicazione'] for row in cursor.fetchall()]

        # New queries for stats cards
        cursor.execute("SELECT COUNT(*) AS total_products FROM prodotti")
        total_products = cursor.fetchone()['total_products']

        cursor.execute("SELECT COUNT(*) AS low_stock_count FROM giacenze WHERE quantita < 10")
        low_stock_count = cursor.fetchone()['low_stock_count']

        cursor.execute("SELECT COUNT(*) AS warehouses_count FROM magazzini")
        warehouses_count = cursor.fetchone()['warehouses_count']

        cursor.execute("SELECT COUNT(*) AS movements_today FROM movimenti WHERE DATE(data_ora) = CURDATE()")
        movements_today = cursor.fetchone()['movements_today']

    except Error as e:
        giacenze = []
        magazzini_opzioni = []
        stati_opzioni = []
        ubicazioni_opzioni = []
        total_products = 0
        low_stock_count = 0
        warehouses_count = 0
        movements_today = 0
        flash(f"Errore nel recupero delle giacenze o filtri: {e}", "error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template("index.html", giacenze=giacenze,
                           filtro_codice=filtro_codice,
                           filtro_nome=filtro_nome,
                           filtro_magazzino=filtro_magazzino,
                           filtro_stato=filtro_stato,
                           filtro_ubicazione=filtro_ubicazione,
                           ordine=ordine,
                           magazzini_opzioni=magazzini_opzioni,
                           stati_opzioni=stati_opzioni,
                           ubicazioni_opzioni=ubicazioni_opzioni,
                           total_products=total_products,
                           low_stock_count=low_stock_count,
                           warehouses_count=warehouses_count,
                           movements_today=movements_today)

# Pagina per registrare un movimento
@app.route('/movimento', methods=['GET', 'POST'])
def movimento():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == "POST":
        giacenza_updated = False
        try:
            prodotto_id = int(request.form["prodotto_id"])
            da_stato = request.form.get("da_stato") or None
            a_stato = request.form.get("a_stato") or None
            da_magazzino_id = request.form.get("da_magazzino_id") or None
            a_magazzino_id = request.form.get("a_magazzino_id") or None
            da_ubicazione = request.form.get("da_ubicazione") or None
            a_ubicazione = request.form.get("a_ubicazione") or None
            quantita = int(request.form["quantita"])
            note = request.form.get("note")
            user_id = session.get('user_id')  # <--- aggiungi questa riga

            if quantita <= 0:
                flash("La quantità deve essere un numero positivo.", "error")
                raise ValueError("Quantità non valida")

            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True, buffered=True)

            # If magazzino_id is None, try to get default magazzino_id for prodotto from giacenze
            if not da_magazzino_id:
                cursor.execute("SELECT magazzino_id FROM giacenze WHERE prodotto_id = %s LIMIT 1", (prodotto_id,))
                result = cursor.fetchone()
                if result and result.get('magazzino_id'):
                    da_magazzino_id = result['magazzino_id']

            if not a_magazzino_id:
                cursor.execute("SELECT magazzino_id FROM giacenze WHERE prodotto_id = %s LIMIT 1", (prodotto_id,))
                result = cursor.fetchone()
                if result and result.get('magazzino_id'):
                    a_magazzino_id = result['magazzino_id']

            # Inserimento movimento (ora con user_id e tipo_movimento)
            # Determina il tipo di movimento basandosi sugli stati
            if not da_stato and a_stato == 'IN_MAGAZZINO':
                tipo_mov = 'CARICO'
            elif da_stato == 'IN_MAGAZZINO' and a_stato != 'IN_MAGAZZINO':
                tipo_mov = 'SCARICO'
            elif da_stato == 'IN_MAGAZZINO' and a_stato == 'IN_MAGAZZINO':
                tipo_mov = 'TRASFERIMENTO'
            else:
                tipo_mov = 'TRASFERIMENTO'  # default per altri casi
            
            cursor.execute("""
                INSERT INTO movimenti (
                    prodotto_id, da_magazzino_id, a_magazzino_id, da_ubicazione, a_ubicazione, quantita, note, user_id, stato, tipo_movimento
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (prodotto_id, da_magazzino_id, a_magazzino_id, da_ubicazione, a_ubicazione, quantita, note, user_id, a_stato, tipo_mov))
            conn.commit()

            # Aggiorna giacenza di partenza
            if da_stato:
                query = """
                    SELECT * FROM giacenze WHERE prodotto_id = %s AND stato = %s
                """
                params = [prodotto_id, da_stato]
                if da_magazzino_id:
                    query += " AND magazzino_id = %s"
                    params.append(da_magazzino_id)
                else:
                    query += " AND magazzino_id IS NULL"
                if da_ubicazione:
                    query += " AND ubicazione = %s"
                    params.append(da_ubicazione)
                else:
                    query += " AND (ubicazione IS NULL OR ubicazione = '')"
                cursor.execute(query, params)
                da_giacenza = cursor.fetchone()

                if da_giacenza:
                    nuova_quantita = da_giacenza["quantita"] - quantita
                    if nuova_quantita <= 0:
                        cursor.execute("DELETE FROM giacenze WHERE id = %s", (da_giacenza["id"],))
                    else:
                        cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s",
                                       (nuova_quantita, da_giacenza["id"]))
                    conn.commit()
                    giacenza_updated = True

            # Aggiorna giacenza di destinazione
            if a_stato:
                query = """
                    SELECT * FROM giacenze WHERE prodotto_id = %s AND stato = %s
                """
                params = [prodotto_id, a_stato]
                if a_magazzino_id:
                    query += " AND magazzino_id = %s"
                    params.append(a_magazzino_id)
                else:
                    query += " AND magazzino_id IS NULL"
                if a_ubicazione:
                    query += " AND ubicazione = %s"
                    params.append(a_ubicazione)
                else:
                    query += " AND (ubicazione IS NULL OR ubicazione = '')"
                # Cerca anche per nota identica
                query_note = query + " AND (note = %s OR (note IS NULL AND %s IS NULL))"
                params_note = params + [note, note]
                cursor.execute(query_note, params_note)
                a_giacenza = cursor.fetchone()

                if a_giacenza:
                    nuova_quantita = a_giacenza["quantita"] + quantita
                    cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s",
                                   (nuova_quantita, a_giacenza["id"]))
                else:
                    cursor.execute("""
                        INSERT INTO giacenze (prodotto_id, magazzino_id, ubicazione, stato, quantita, note)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (prodotto_id, a_magazzino_id, a_ubicazione, a_stato, quantita, note))
                conn.commit()
                giacenza_updated = True

            if giacenza_updated:
                flash("Movimento e giacenza aggiornati con successo.", "success")
            else:
                flash("Movimento registrato, ma nessuna giacenza aggiornata.", "warning")

            # Resta sulla pagina movimento per registrare più movimenti in sequenza
            return redirect(url_for("movimento"))

        except ValueError:
            # Input validation error already flashed
            pass
        except Error as e:
            flash(f"Errore nel database: {e}", "error")
        except Exception as e:
            flash(f"Errore imprevisto: {e}", "error")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()

    # dati per il form
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True, buffered=True)
        # Usa la lista statica degli stati
        stati = STATI_DISPONIBILI.copy()
        cursor.execute("SELECT id, nome FROM magazzini")
        magazzini = []  # Ora caricati dinamicamente via AJAX
        cursor.execute("SELECT id, nome_prodotto, codice_prodotto FROM prodotti")
        prodotti = cursor.fetchall()
    except Error as e:
        stati = STATI_DISPONIBILI.copy()
        magazzini = []
        prodotti = []
        flash(f"Errore nel recupero dati per il form: {e}", "error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return render_template("movimento.html", prodotti=prodotti, magazzini=magazzini, stati=stati)


@app.route('/nuovo-prodotto', methods=['GET', 'POST'])
def nuovo_prodotto():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nome_prodotto = request.form.get('nome_prodotto')
        codice_prodotto = request.form.get('codice_prodotto')
        quantita = request.form.get('quantita')
        ubicazione = request.form.get('ubicazione')
        magazzino_id = request.form.get('magazzino_id')
        stato = request.form.get('stato')

        if not nome_prodotto or not codice_prodotto or not quantita or not magazzino_id or not stato:
            flash('Nome prodotto, codice prodotto, magazzino, stato e quantità sono obbligatori.', 'error')
            return redirect(url_for('nuovo_prodotto'))

        try:
            quantita_int = int(quantita)
            if quantita_int < 0:
                flash('La quantità deve essere un numero positivo.', 'error')
                return redirect(url_for('nuovo_prodotto'))
        except ValueError:
            flash('La quantità deve essere un numero valido.', 'error')
            return redirect(url_for('nuovo_prodotto'))

        try:
            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True)

            # Controlla se il codice prodotto esiste già
            cursor.execute("SELECT id FROM prodotti WHERE codice_prodotto = %s", (codice_prodotto,))
            existing = cursor.fetchone()
            if existing:
                flash('Codice prodotto già esistente. Scegli un altro codice.', 'error')
                cursor.close()
                conn.close()
                return redirect(url_for('nuovo_prodotto'))

            # Insert new product
            cursor.execute("INSERT INTO prodotti (nome_prodotto, codice_prodotto) VALUES (%s, %s)",
                           (nome_prodotto, codice_prodotto))
            prodotto_id = cursor.lastrowid

            # Insert into giacenze con magazzino_id e stato scelto
            cursor.execute("""
                INSERT INTO giacenze (prodotto_id, magazzino_id, ubicazione, stato, quantita)
                VALUES (%s, %s, %s, %s, %s)
            """, (prodotto_id, magazzino_id, ubicazione, stato, quantita_int))

            conn.commit()
            cursor.close()
            conn.close()
            flash('Prodotto e giacenza registrati con successo.', 'success')
            return redirect(url_for('index'))
        except mysql.connector.IntegrityError as ie:
            flash(f'Codice prodotto già esistente. Scegli un altro codice. Dettagli: {ie}', 'error')
            return redirect(url_for('nuovo_prodotto'))
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            flash(f'Errore durante la registrazione del prodotto: {e}', 'error')
            print("Exception in /nuovo-prodotto POST:\n", error_details)
            return redirect(url_for('nuovo_prodotto'))

    # Carica lista prodotti con quantità totale per la visualizzazione
    prodotti_lista = []
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.id, p.nome_prodotto, p.codice_prodotto, 
                   COALESCE(SUM(g.quantita), 0) as quantita_totale
            FROM prodotti p
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            GROUP BY p.id, p.nome_prodotto, p.codice_prodotto
            ORDER BY p.nome_prodotto ASC
        """)
        prodotti_lista = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Errore caricamento prodotti: {e}")

    return render_template('nuovo-prodotto.html', prodotti=prodotti_lista)


# API per ottenere le giacenze di un prodotto
@app.route('/api/prodotto/<int:prodotto_id>/giacenze', methods=['GET'])
def api_giacenze_prodotto(prodotto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.id, g.quantita, g.stato, g.ubicazione, g.note, m.nome as magazzino_nome
            FROM giacenze g
            LEFT JOIN magazzini m ON g.magazzino_id = m.id
            WHERE g.prodotto_id = %s
            ORDER BY g.stato, g.ubicazione
        """, (prodotto_id,))
        giacenze = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'giacenze': giacenze})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# API per ottenere i dettagli di un prodotto
@app.route('/api/prodotto/<int:prodotto_id>', methods=['GET'])
def api_get_prodotto(prodotto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nome_prodotto, codice_prodotto FROM prodotti WHERE id = %s", (prodotto_id,))
        prodotto = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not prodotto:
            return jsonify({'error': 'Prodotto non trovato'}), 404
        
        return jsonify({'prodotto': prodotto})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# API per modificare un prodotto
@app.route('/api/prodotto/<int:prodotto_id>', methods=['PUT'])
def api_modifica_prodotto(prodotto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    data = request.get_json()
    nome_prodotto = data.get('nome_prodotto', '').strip()
    codice_prodotto = data.get('codice_prodotto', '').strip()
    
    if not nome_prodotto or not codice_prodotto:
        return jsonify({'error': 'Nome e codice prodotto sono obbligatori'}), 400
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Verifica che il codice non sia già usato da un altro prodotto
        cursor.execute("SELECT id FROM prodotti WHERE codice_prodotto = %s AND id != %s", (codice_prodotto, prodotto_id))
        existing = cursor.fetchone()
        if existing:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Codice prodotto già in uso da un altro prodotto'}), 400
        
        cursor.execute("""
            UPDATE prodotti SET nome_prodotto = %s, codice_prodotto = %s WHERE id = %s
        """, (nome_prodotto, codice_prodotto, prodotto_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Prodotto aggiornato con successo'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# API per eliminare un prodotto (e tutte le sue giacenze)
@app.route('/api/prodotto/<int:prodotto_id>', methods=['DELETE'])
def api_elimina_prodotto(prodotto_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Prima elimina tutte le giacenze associate
        cursor.execute("DELETE FROM giacenze WHERE prodotto_id = %s", (prodotto_id,))
        
        # Poi elimina il prodotto
        cursor.execute("DELETE FROM prodotti WHERE id = %s", (prodotto_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Prodotto e giacenze eliminate con successo'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========================================
# NOTE: Le routes /login, /logout, /register sono state
# spostate in routes/auth.py (auth_bp blueprint)
# ========================================


# ========================================
# GESTIONE SOGLIE E NOTIFICHE
# ========================================

@app.route('/api/soglie_data')
def api_soglie_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera tutti i prodotti per il dropdown
        cursor.execute("""
            SELECT DISTINCT codice_prodotto, nome_prodotto 
            FROM prodotti 
            ORDER BY nome_prodotto
        """)
        prodotti = cursor.fetchall()
        
        # Recupera tutte le soglie configurate con quantità attuale (solo per l'utente corrente)
        cursor.execute("""
            SELECT 
                pt.id,
                pt.codice_prodotto,
                pt.nome_prodotto,
                pt.soglia_minima,
                pt.notifica_attiva,
                COALESCE(SUM(g.quantita), 0) as quantita_attuale
            FROM product_thresholds pt
            LEFT JOIN prodotti p ON pt.codice_prodotto COLLATE utf8mb4_unicode_ci = p.codice_prodotto COLLATE utf8mb4_unicode_ci
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            WHERE pt.user_id = %s
            GROUP BY pt.id, pt.codice_prodotto, pt.nome_prodotto, pt.soglia_minima, pt.notifica_attiva
            ORDER BY pt.nome_prodotto
        """, (session['user_id'],))
        soglie = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({'soglie': soglie, 'prodotti': prodotti})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/gestione_soglie')
def gestione_soglie():
    if 'user_id' not in session:
        flash('Devi effettuare il login per accedere.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera tutti i prodotti per il dropdown
        cursor.execute("""
            SELECT DISTINCT codice_prodotto, nome_prodotto 
            FROM prodotti 
            ORDER BY nome_prodotto
        """)
        prodotti = cursor.fetchall()
        
        # Recupera tutte le soglie configurate con quantità attuale (solo per l'utente corrente)
        cursor.execute("""
            SELECT 
                pt.id,
                pt.codice_prodotto,
                pt.nome_prodotto,
                pt.soglia_minima,
                pt.notifica_attiva,
                COALESCE(SUM(g.quantita), 0) as quantita_attuale
            FROM product_thresholds pt
            LEFT JOIN prodotti p ON pt.codice_prodotto COLLATE utf8mb4_unicode_ci = p.codice_prodotto COLLATE utf8mb4_unicode_ci
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            WHERE pt.user_id = %s
            GROUP BY pt.id, pt.codice_prodotto, pt.nome_prodotto, pt.soglia_minima, pt.notifica_attiva
            ORDER BY pt.nome_prodotto
        """, (session['user_id'],))
        soglie = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('gestione_soglie.html', soglie=soglie, prodotti=prodotti)
    except Exception as e:
        flash(f'Errore nel caricamento delle soglie: {e}', 'error')
        return redirect(url_for('index'))


@app.route('/add_threshold', methods=['POST'])
def add_threshold():
    if 'user_id' not in session:
        flash('Devi effettuare il login.', 'error')
        return redirect(url_for('auth.login'))
    
    codice_prodotto = request.form.get('codice_prodotto')
    soglia_minima = request.form.get('soglia_minima')
    notifica_attiva = request.form.get('notifica_attiva') == 'true'
    
    if not codice_prodotto or not soglia_minima:
        flash('Tutti i campi sono obbligatori.', 'error')
        return redirect(request.referrer or url_for('index'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera il nome del prodotto
        cursor.execute("SELECT nome_prodotto FROM prodotti WHERE codice_prodotto = %s", (codice_prodotto,))
        prodotto = cursor.fetchone()
        
        if not prodotto:
            flash('Prodotto non trovato.', 'error')
            return redirect(request.referrer or url_for('index'))
        
        # Inserisci la soglia con user_id
        cursor.execute("""
            INSERT INTO product_thresholds (user_id, codice_prodotto, nome_prodotto, soglia_minima, notifica_attiva)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], codice_prodotto, prodotto['nome_prodotto'], soglia_minima, notifica_attiva))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Soglia aggiunta con successo!', 'success')
        
        # Controlla immediatamente se va generata una notifica
        check_and_create_notifications()
        
    except mysql.connector.IntegrityError:
        flash('Esiste già una soglia per questo prodotto.', 'error')
    except Exception as e:
        flash(f'Errore durante l\'aggiunta della soglia: {e}', 'error')
    
    return redirect(request.referrer or url_for('index'))


@app.route('/update_threshold', methods=['POST'])
def update_threshold():
    if 'user_id' not in session:
        flash('Devi effettuare il login.', 'error')
        return redirect(url_for('auth.login'))
    
    threshold_id = request.form.get('threshold_id')
    soglia_minima = request.form.get('soglia_minima')
    notifica_attiva = request.form.get('notifica_attiva') == 'true'
    
    if not threshold_id or not soglia_minima:
        flash('Dati mancanti.', 'error')
        return redirect(request.referrer or url_for('index'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE product_thresholds 
            SET soglia_minima = %s, notifica_attiva = %s
            WHERE id = %s AND user_id = %s
        """, (soglia_minima, notifica_attiva, threshold_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Soglia aggiornata con successo!', 'success')
        
        # Controlla se va generata una notifica
        check_and_create_notifications()
        
    except Exception as e:
        flash(f'Errore durante l\'aggiornamento: {e}', 'error')
    
    return redirect(request.referrer or url_for('index'))


@app.route('/toggle_threshold', methods=['POST'])
def toggle_threshold():
    if 'user_id' not in session:
        flash('Devi effettuare il login.', 'error')
        return redirect(url_for('auth.login'))
    
    threshold_id = request.form.get('threshold_id')
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE product_thresholds 
            SET notifica_attiva = NOT notifica_attiva
            WHERE id = %s AND user_id = %s
        """, (threshold_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Stato notifica aggiornato!', 'success')
    except Exception as e:
        flash(f'Errore: {e}', 'error')
    
    return redirect(request.referrer or url_for('index'))


@app.route('/delete_threshold', methods=['POST'])
def delete_threshold():
    if 'user_id' not in session:
        flash('Devi effettuare il login.', 'error')
        return redirect(url_for('auth.login'))
    
    threshold_id = request.form.get('threshold_id')
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM product_thresholds WHERE id = %s AND user_id = %s", (threshold_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Soglia eliminata con successo!', 'success')
    except Exception as e:
        flash(f'Errore durante l\'eliminazione: {e}', 'error')
    
    return redirect(request.referrer or url_for('index'))


def check_and_create_notifications():
    """
    Funzione che controlla tutte le soglie attive e crea notifiche
    per i prodotti che sono sotto la soglia minima (per ogni utente)
    """
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Trova tutti i prodotti sotto soglia per ogni utente
        cursor.execute("""
            SELECT 
                pt.user_id,
                pt.codice_prodotto,
                pt.nome_prodotto,
                pt.soglia_minima,
                COALESCE(SUM(g.quantita), 0) as quantita_attuale,
                m.nome as magazzino
            FROM product_thresholds pt
            LEFT JOIN prodotti p ON pt.codice_prodotto COLLATE utf8mb4_unicode_ci = p.codice_prodotto COLLATE utf8mb4_unicode_ci
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            LEFT JOIN magazzini m ON g.magazzino_id = m.id
            WHERE pt.notifica_attiva = TRUE
            GROUP BY pt.user_id, pt.codice_prodotto, pt.nome_prodotto, pt.soglia_minima, m.nome
            HAVING quantita_attuale <= pt.soglia_minima
        """)
        
        prodotti_sotto_soglia = cursor.fetchall()
        
        for prodotto in prodotti_sotto_soglia:
            # Controlla se esiste già una notifica non visualizzata per questo prodotto e utente
            cursor.execute("""
                SELECT id FROM notifications 
                WHERE codice_prodotto = %s AND user_id = %s AND visualizzata = FALSE
                LIMIT 1
            """, (prodotto['codice_prodotto'], prodotto['user_id']))
            
            existing = cursor.fetchone()
            
            if not existing:
                # Crea nuova notifica per questo utente specifico
                cursor.execute("""
                    INSERT INTO notifications 
                    (user_id, codice_prodotto, nome_prodotto, quantita_attuale, soglia_minima, magazzino)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    prodotto['user_id'],
                    prodotto['codice_prodotto'],
                    prodotto['nome_prodotto'],
                    prodotto['quantita_attuale'],
                    prodotto['soglia_minima'],
                    prodotto.get('magazzino', 'N/A')
                ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Errore nel controllo soglie: {e}")


@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera notifiche non visualizzate per l'utente corrente
        cursor.execute("""
            SELECT 
                id,
                codice_prodotto,
                nome_prodotto,
                quantita_attuale,
                soglia_minima,
                magazzino,
                data_notifica
            FROM notifications
            WHERE visualizzata = FALSE AND user_id = %s
            ORDER BY data_notifica DESC
        """, (session['user_id'],))
        
        notifiche = cursor.fetchall()
        
        # Converti datetime in stringa per JSON
        for n in notifiche:
            if n.get('data_notifica'):
                n['data_notifica'] = n['data_notifica'].strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'count': len(notifiche),
            'notifications': notifiche
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE notifications 
            SET visualizzata = TRUE, data_visualizzazione = NOW()
            WHERE id = %s AND user_id = %s
        """, (notification_id, session['user_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE notifications 
            SET visualizzata = TRUE, data_visualizzazione = NOW()
            WHERE visualizzata = FALSE AND user_id = %s
        """, (session['user_id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/esporta_magazzino')
def esporta_magazzino():
    # Recupera tutte le giacenze dal database
    giacenze = get_all_giacenze()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    output = io.StringIO()
    output.write("PHARMAGEST - ESPORTAZIONE MAGAZZINO\n")
    output.write(f"Data esportazione: {now}\n\n")

    # Definisci larghezza colonne
    widths = {
        "codice": 14,
        "prodotto": 32,
        "magazzino": 20,
        "ubicazione": 18,
        "stato": 13,
        "quantita": 9,
        "note": 30
    }

    # Intestazione
    header = (
        f"{'Codice':<{widths['codice']}}"
        f"{'Prodotto':<{widths['prodotto']}}"
        f"{'Magazzino':<{widths['magazzino']}}"
        f"{'Ubicazione':<{widths['ubicazione']}}"
        f"{'Stato':<{widths['stato']}}"
        f"{'Quantità':>{widths['quantita']}}  "
        f"{'Note'}"
    )
    output.write(header + "\n")
    output.write("-" * (sum(widths.values()) + 14) + "\n")

    for g in giacenze:
        output.write(
            f"{str(g['codice_prodotto'])[:widths['codice']-1]:<{widths['codice']}}"
            f"{str(g['nome_prodotto'])[:widths['prodotto']-1]:<{widths['prodotto']}}"
            f"{str(g['magazzino'] or '')[:widths['magazzino']-1]:<{widths['magazzino']}}"
            f"{str(g['ubicazione'] or '')[:widths['ubicazione']-1]:<{widths['ubicazione']}}"
            f"{str(g['stato'] or '')[:widths['stato']-1]:<{widths['stato']}}"
            f"{str(g['quantita']):>{widths['quantita']}}  "
            f"{str(g['note'] or '')}\n"
        )
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=magazzino_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response

@app.route('/esporta_magazzino_xlsx')
def esporta_magazzino_xlsx():
    giacenze = get_all_giacenze()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    workbook = xlsxwriter.Workbook(temp.name)
    worksheet = workbook.add_worksheet("Magazzino")

    # Formattazione header
    bold = workbook.add_format({'bold': True, 'bg_color': '#e3f2fd'})
    date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy hh:mm'})

    # Scrivi la data di esportazione
    worksheet.write('A1', 'PHARMAGEST - ESPORTAZIONE MAGAZZINO')
    worksheet.write('A2', f'Data esportazione: {now}')

    # Intestazioni colonne
    headers = ["Codice", "Prodotto", "Magazzino", "Ubicazione", "Stato", "Quantità", "Note"]
    for col, h in enumerate(headers):
        worksheet.write(3, col, h, bold)

    # Dati
    for row, g in enumerate(giacenze, start=4):
        worksheet.write(row, 0, g['codice_prodotto'])
        worksheet.write(row, 1, g['nome_prodotto'])
        worksheet.write(row, 2, g['magazzino'] or '')
        worksheet.write(row, 3, g['ubicazione'] or '')
        worksheet.write(row, 4, g['stato'] or '')
        worksheet.write(row, 5, g['quantita'])
        worksheet.write(row, 6, g['note'] or '')

    worksheet.set_column(0, 0, 15)
    worksheet.set_column(1, 1, 30)
    worksheet.set_column(2, 2, 20)
    worksheet.set_column(3, 3, 18)
    worksheet.set_column(4, 4, 13)
    worksheet.set_column(5, 5, 9)
    worksheet.set_column(6, 6, 30)

    workbook.close()
    temp.seek(0)
    filename = f"magazzino_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = send_file(temp.name, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    # Pulizia file temporaneo dopo invio
    @response.call_on_close
    def cleanup():
        try:
            os.remove(temp.name)
        except Exception:
            pass
    return response

def get_all_giacenze():
    """
    Recupera tutte le giacenze dal database con tutte le informazioni necessarie per l'esportazione.
    """
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                p.codice_prodotto,
                p.nome_prodotto,
                m.nome AS magazzino,
                g.ubicazione,
                g.stato,
                g.quantita,
                g.note
            FROM giacenze g
            JOIN prodotti p ON g.prodotto_id = p.id
            LEFT JOIN magazzini m ON g.magazzino_id = m.id
            ORDER BY p.codice_prodotto ASC, m.nome ASC, g.ubicazione ASC
        """)
        giacenze = cursor.fetchall()
        cursor.close()
        conn.close()
        return giacenze
    except Exception as e:
        # In caso di errore, ritorna una lista vuota
        return []

from flask import request

@app.route('/elimina_giacenza/<int:giacenza_id>', methods=['POST'])
def elimina_giacenza(giacenza_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM giacenze WHERE id = %s", (giacenza_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Giacenza eliminata con successo.', 'success')
    except Exception as e:
        flash(f'Errore durante l\'eliminazione della giacenza: {e}', 'error')
    return redirect(url_for('index'))

@app.route('/logmovimenti')
def logmovimenti():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera movimenti unificati da entrambe le tabelle
        cursor.execute("""
            SELECT 
                mv.data_ora,
                u.username COLLATE utf8mb4_unicode_ci AS username,
                p.nome_prodotto COLLATE utf8mb4_unicode_ci AS nome_prodotto,
                m1.nome COLLATE utf8mb4_unicode_ci AS da_magazzino,
                m2.nome COLLATE utf8mb4_unicode_ci AS a_magazzino,
                mv.da_ubicazione COLLATE utf8mb4_unicode_ci AS da_ubicazione,
                mv.a_ubicazione COLLATE utf8mb4_unicode_ci AS a_ubicazione,
                mv.quantita,
                mv.note COLLATE utf8mb4_unicode_ci AS note,
                mv.stato COLLATE utf8mb4_unicode_ci AS stato,
                mv.tipo_movimento COLLATE utf8mb4_unicode_ci AS tipo_movimento
            FROM movimenti mv
            LEFT JOIN utenti u ON mv.user_id = u.id
            LEFT JOIN prodotti p ON mv.prodotto_id = p.id
            LEFT JOIN magazzini m1 ON mv.da_magazzino_id = m1.id
            LEFT JOIN magazzini m2 ON mv.a_magazzino_id = m2.id
            
            UNION ALL
            
            SELECT 
                ls.data_ora,
                u.username COLLATE utf8mb4_unicode_ci AS username,
                p.nome_prodotto COLLATE utf8mb4_unicode_ci AS nome_prodotto,
                NULL AS da_magazzino,
                NULL AS a_magazzino,
                NULL AS da_ubicazione,
                NULL AS a_ubicazione,
                ls.quantita,
                CONCAT('Tipo scarico: ', COALESCE(ls.tipo_scarico, ''), 
                       CASE WHEN ls.note IS NOT NULL AND ls.note != '' 
                            THEN CONCAT(' - ', ls.note) 
                            ELSE '' END) COLLATE utf8mb4_unicode_ci AS note,
                NULL AS stato,
                'SCARICO' COLLATE utf8mb4_unicode_ci AS tipo_movimento
            FROM log_scarichi ls
            LEFT JOIN utenti u ON ls.user_id = u.id
            LEFT JOIN prodotti p ON ls.prodotto_id = p.id
            
            ORDER BY data_ora DESC
        """)
        movimenti = cursor.fetchall()
        
        # Recupera lista magazzini per il filtro
        cursor.execute("SELECT DISTINCT nome FROM magazzini ORDER BY nome")
        magazzini_opzioni = [row['nome'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
    except Exception as e:
        movimenti = []
        magazzini_opzioni = []
        flash(f"Errore nel recupero dei movimenti: {e}", "error")
    return render_template("logmovimenti.html", movimenti=movimenti, magazzini_opzioni=magazzini_opzioni)

@app.route('/scaricomerce', methods=['GET', 'POST'])
def scaricomerce():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Solo prodotti in magazzino
    import re
    def natural_key(s):
        # Divide la stringa in blocchi numerici e non numerici per ordinamento naturale
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s or '')]

    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT p.id, p.nome_prodotto, p.codice_prodotto
            FROM prodotti p
            JOIN giacenze g ON g.prodotto_id = p.id
            WHERE g.stato = 'IN_MAGAZZINO' AND g.quantita > 0
            ORDER BY p.nome_prodotto ASC
        """)
        prodotti_magazzino = cursor.fetchall()
        cursor.execute("""
            SELECT DISTINCT ubicazione FROM giacenze 
            WHERE stato = 'IN_MAGAZZINO' AND ubicazione IS NOT NULL AND ubicazione != '' AND quantita > 0
            ORDER BY ubicazione ASC
        """)
        ubicazioni_magazzino = [row['ubicazione'] for row in cursor.fetchall()]
        # Ordinamento naturale
        ubicazioni_magazzino = sorted(ubicazioni_magazzino, key=natural_key)
        cursor.close()
        conn.close()
    except Exception as e:
        prodotti_magazzino = []
        ubicazioni_magazzino = []
        flash(f"Errore nel caricamento dati: {e}", "error")

    if request.method == 'POST':
        prodotto_id = request.form.get('prodotto_id')
        ubicazione = request.form.get('ubicazione')
        quantita = request.form.get('quantita')
        note = request.form.get('note')
        if not prodotto_id or not quantita:
            flash("Prodotto e quantità sono obbligatori.", "error")
            return redirect(url_for('scaricomerce'))
        try:
            quantita = int(quantita)
            if quantita <= 0:
                flash("La quantità deve essere positiva.", "error")
                return redirect(url_for('scaricomerce'))
        except ValueError:
            flash("Quantità non valida.", "error")
            return redirect(url_for('scaricomerce'))
        try:
            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM giacenze WHERE prodotto_id = %s AND stato = 'IN_MAGAZZINO'"
            params = [prodotto_id]
            if ubicazione:
                query += " AND ubicazione = %s"
                params.append(ubicazione)
            cursor.execute(query, params)
            giacenza = cursor.fetchone()
            if not giacenza:
                flash("Giacenza non trovata per il prodotto e ubicazione selezionati.", "error")
            elif giacenza['quantita'] < quantita:
                flash("Quantità da scaricare superiore alla giacenza disponibile.", "error")
            else:
                nuova_quantita = giacenza['quantita'] - quantita
                if nuova_quantita == 0:
                    cursor.execute("DELETE FROM giacenze WHERE id = %s", (giacenza['id'],))
                else:
                    cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s", (nuova_quantita, giacenza['id']))
                
                # Log dello scarico
                cursor.execute("""
                    INSERT INTO log_scarichi (prodotto_id, quantita, note, user_id, tipo_scarico)
                    VALUES (%s, %s, %s, %s, %s)
                """, (prodotto_id, quantita, note, session.get('user_id'), 'DA_MAGAZZINO'))
                
                conn.commit()
                flash("Scarico effettuato con successo.", "success")
                
                # Controlla soglie dopo lo scarico
                check_and_create_notifications()
                
            cursor.close()
            conn.close()
        except Exception as e:
            flash(f"Errore durante lo scarico: {e}", "error")
        return redirect(url_for('scaricomerce'))

    return render_template(
        'scaricomerce.html',
        prodotti_magazzino=prodotti_magazzino,
        ubicazioni_magazzino=ubicazioni_magazzino
    )

@app.route('/scarico_merce_non_in_magazzino', methods=['GET', 'POST'])
def scarico_merce_non_in_magazzino():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    filtro_stato = request.args.get('filtro_stato', '')
    filtro_note = request.args.get('filtro_note', '')

    # Gestione scarico multiplo POST
    if request.method == 'POST' and request.form.getlist('prodotti_selezionati'):
        prodotti_selezionati = request.form.getlist('prodotti_selezionati')
        filtro_stato = request.form.get('filtro_stato', '')
        filtro_note = request.form.get('filtro_note', '')
        try:
            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True)
            
            # Prima recupera i dati dei prodotti da scaricare per il log
            ids_tuple = tuple(int(pid) for pid in prodotti_selezionati)
            if ids_tuple:
                if len(ids_tuple) == 1:
                    cursor.execute("SELECT g.*, p.id as prodotto_id FROM giacenze g JOIN prodotti p ON g.prodotto_id = p.id WHERE g.id = %s", (ids_tuple[0],))
                else:
                    format_strings = ','.join(['%s'] * len(ids_tuple))
                    cursor.execute(f"SELECT g.*, p.id as prodotto_id FROM giacenze g JOIN prodotti p ON g.prodotto_id = p.id WHERE g.id IN ({format_strings})", ids_tuple)
                
                giacenze_da_scaricare = cursor.fetchall()
                
                # Inserisci i log per ogni prodotto scaricato
                for giacenza in giacenze_da_scaricare:
                    cursor.execute("""
                        INSERT INTO log_scarichi (prodotto_id, quantita, note, user_id, tipo_scarico)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (giacenza['prodotto_id'], giacenza['quantita'], giacenza['note'], session.get('user_id'), 'NON_IN_MAGAZZINO'))
                
                # Elimina le giacenze
                if len(ids_tuple) == 1:
                    cursor.execute("DELETE FROM giacenze WHERE id = %s", (ids_tuple[0],))
                else:
                    format_strings = ','.join(['%s'] * len(ids_tuple))
                    cursor.execute(f"DELETE FROM giacenze WHERE id IN ({format_strings})", ids_tuple)
                
                conn.commit()
            cursor.close()
            conn.close()
            flash("Scarico effettuato per i prodotti selezionati.", "success")
        except Exception as e:
            flash(f"Errore durante lo scarico multiplo: {e}", "error")
        return redirect(url_for('scarico_merce_non_in_magazzino', filtro_stato=filtro_stato, filtro_note=filtro_note))

    # ...existing code for loading and rendering...
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        # Usa la lista statica degli stati (escluso IN_MAGAZZINO)
        stati_non_magazzino = [s for s in STATI_DISPONIBILI if s != 'IN_MAGAZZINO']
        query = """
            SELECT g.id, p.codice_prodotto, p.nome_prodotto, g.stato, g.quantita, g.note
            FROM giacenze g
            JOIN prodotti p ON g.prodotto_id = p.id
            WHERE g.stato != 'IN_MAGAZZINO'
        """
        params = []
        if filtro_stato:
            query += " AND g.stato = %s"
            params.append(filtro_stato)
        if filtro_note:
            query += " AND g.note LIKE %s"
            params.append(f"%{filtro_note}%")
        cursor.execute(query, params)
        prodotti_non_magazzino = cursor.fetchall()
    except Exception as e:
        stati_non_magazzino = []
        prodotti_non_magazzino = []
        flash(f"Errore nel caricamento dati: {e}", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    return render_template(
        'scarico_merce_non_in_magazzino.html',
        stati_non_magazzino=stati_non_magazzino,
        prodotti_non_magazzino=prodotti_non_magazzino,
        filtro_stato=filtro_stato,
        filtro_note=filtro_note
    )

@app.route('/logscarico')
def logscarico():
    # Redirect alla pagina unificata logmovimenti
    return redirect(url_for('logmovimenti'))

@app.route('/carico_merci', methods=['GET', 'POST'])
def carico_merci():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Recupera tutti i prodotti esistenti
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, nome_prodotto, codice_prodotto FROM prodotti ORDER BY nome_prodotto ASC")
        prodotti = cursor.fetchall()
    except Exception as e:
        prodotti = []
        flash(f"Errore nel caricamento prodotti: {e}", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    if request.method == 'POST':
        prodotto_id = request.form.get('prodotto_id')
        quantita = request.form.get('quantita')
        ubicazione = request.form.get('ubicazione', '').strip()
        note = request.form.get('note', '').strip()

        # Validazione base
        try:
            quantita = int(quantita)
        except Exception:
            quantita = None

        if not prodotto_id or not quantita or quantita < 1:
            flash('Seleziona un prodotto e una quantità valida.', 'danger')
            return redirect(url_for('carico_merci'))


        try:
            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True)

            # Recupera la giacenza esistente per il prodotto (e ubicazione se specificata)
            query = "SELECT * FROM giacenze WHERE prodotto_id = %s AND stato = 'IN_MAGAZZINO'"
            params = [prodotto_id]
            if ubicazione:
                query += " AND ubicazione = %s"
                params.append(ubicazione)
            else:
                query += " AND (ubicazione IS NULL OR ubicazione = '')"
            cursor.execute(query, params)
            giacenza = cursor.fetchone()

            if giacenza:
                nuova_quantita = giacenza['quantita'] + quantita
                cursor.execute("UPDATE giacenze SET quantita = %s, note = %s WHERE id = %s", (nuova_quantita, note, giacenza['id']))
                # Usa magazzino_id dalla giacenza esistente
                magazzino_id = giacenza['magazzino_id']
                stato = giacenza['stato']
            else:
                # Prima di inserire una nuova giacenza, trova un magazzino_id valido
                # Opzione 1: Prova a recuperare magazzino_id da giacenze esistenti per questo prodotto
                cursor.execute("SELECT magazzino_id FROM giacenze WHERE prodotto_id = %s LIMIT 1", (prodotto_id,))
                info = cursor.fetchone()
                # Opzione 2: Se non ci sono giacenze, usa il primo magazzino disponibile nel sistema
                if info and info['magazzino_id']:
                    magazzino_id = info['magazzino_id']
                else:
                    # Fallback: Usa il primo magazzino disponibile nel sistema
                    cursor.execute("SELECT id FROM magazzini ORDER BY id LIMIT 1")
                    magazzino_result = cursor.fetchone()
                    if not magazzino_result:
                        raise Exception("Nessun magazzino trovato nel sistema")
                    magazzino_id = magazzino_result['id']
                
                # Lo stato per un carico merci è sempre 'IN_MAGAZZINO' (maiuscolo per coerenza)
                stato = 'IN_MAGAZZINO'
                
                cursor.execute("""
                    INSERT INTO giacenze (prodotto_id, magazzino_id, ubicazione, stato, quantita, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (prodotto_id, magazzino_id, ubicazione, stato, quantita, note))

            # Log movimento carico
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, quantita, note, user_id, stato, a_ubicazione, a_magazzino_id, tipo_movimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                prodotto_id,
                quantita,
                note,
                session.get('user_id'),
                stato,
                ubicazione,
                magazzino_id,
                'CARICO'
            ))

            conn.commit()
            cursor.close()
            conn.close()
            flash('Carico effettuato con successo!', 'success')
            
            # Controlla soglie dopo il carico (potrebbe aver riportato sopra soglia)
            check_and_create_notifications()
            
            return redirect(url_for('carico_merci'))

        except Exception as e:
            if 'conn' in locals():
                conn.close()
            flash('Errore durante il carico: {}'.format(str(e)), 'danger')
            return redirect(url_for('carico_merci'))



    return render_template('carico_merci.html', prodotti=prodotti, username=session.get('username'))

@app.route('/modifica_giacenza/<int:giacenza_id>', methods=['POST'])
def modifica_giacenza(giacenza_id):
    from flask import jsonify
    
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        ubicazione = request.form.get('ubicazione', '').strip()
        stato = request.form.get('stato', '').strip()
        quantita = request.form.get('quantita', '').strip()
        note = request.form.get('note', '').strip()
        
        # Validazione quantità
        try:
            quantita_nuova = int(quantita)
            if quantita_nuova < 0:
                flash('La quantità deve essere un numero positivo.', 'error')
                return redirect(url_for('index'))
        except ValueError:
            flash('Quantità non valida.', 'error')
            return redirect(url_for('index'))
        
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera la giacenza originale
        cursor.execute("SELECT * FROM giacenze g JOIN prodotti p ON g.prodotto_id = p.id WHERE g.id = %s", (giacenza_id,))
        giacenza_originale = cursor.fetchone()
        if not giacenza_originale:
            flash('Giacenza non trovata.', 'error')
            return redirect(url_for('index'))
        
        quantita_originale = giacenza_originale['quantita']
        differenza_quantita = quantita_nuova - quantita_originale
        stato_originale = giacenza_originale['stato']
        
        # Compensazione necessaria se:
        # La giacenza originale NON è in magazzino (stato != 'IN_MAGAZZINO') E c'è una variazione di quantità
        if differenza_quantita != 0 and stato_originale != 'IN_MAGAZZINO':
            if differenza_quantita > 0:
                # Aumento quantità fuori magazzino - serve prelievo dal magazzino
                cursor.execute("""
                    SELECT g.id, g.ubicazione, g.quantita, m.nome as magazzino_nome
                    FROM giacenze g 
                    JOIN magazzini m ON g.magazzino_id = m.id
                    WHERE g.prodotto_id = %s AND g.stato = 'IN_MAGAZZINO' AND g.id != %s AND g.quantita > 0
                    ORDER BY g.ubicazione ASC
                """, (giacenza_originale['prodotto_id'], giacenza_id))
                giacenze_magazzino = cursor.fetchall()
                
                quantita_totale_disponibile = sum(g['quantita'] for g in giacenze_magazzino)
                if quantita_totale_disponibile < differenza_quantita:
                    return jsonify({
                        'error': True,
                        'message': f'Quantità disponibile in magazzino insufficiente. Disponibili: {quantita_totale_disponibile}, Richiesti: {differenza_quantita}'
                    })
                
                if not giacenze_magazzino:
                    return jsonify({
                        'error': True,
                        'message': 'Non ci sono giacenze di questo prodotto in magazzino da cui prelevare.'
                    })
            else:
                # Diminuzione quantità fuori magazzino - serve restituzione
                cursor.execute("""
                    SELECT DISTINCT
                        COALESCE(g.id, -1) as id,
                        COALESCE(g.ubicazione, all_loc.ubicazione) as ubicazione,
                        COALESCE(g.quantita, 0) as quantita,
                        m.nome as magazzino_nome,
                        CASE WHEN g.id IS NOT NULL THEN 'esistente' ELSE 'nuova' END as tipo_ubicazione
                    FROM (
                        SELECT DISTINCT ubicazione, magazzino_id FROM giacenze 
                        WHERE ubicazione IS NOT NULL AND ubicazione != '' AND stato = 'IN_MAGAZZINO'
                        UNION
                        SELECT DISTINCT ubicazione, magazzino_id FROM giacenze 
                        WHERE prodotto_id = %s AND id != %s AND stato = 'IN_MAGAZZINO'
                    ) all_loc
                    JOIN magazzini m ON all_loc.magazzino_id = m.id
                    LEFT JOIN giacenze g ON g.ubicazione = all_loc.ubicazione 
                        AND g.prodotto_id = %s AND g.stato = 'IN_MAGAZZINO' AND g.id != %s
                    ORDER BY ubicazione ASC
                """, (giacenza_originale['prodotto_id'], giacenza_id, giacenza_originale['prodotto_id'], giacenza_id))
                giacenze_magazzino = cursor.fetchall()
            
            # Ritorna JSON con le opzioni di compensazione
            return jsonify({
                'need_compensation': True,
                'differenza': differenza_quantita,
                'tipo': 'prelievo' if differenza_quantita > 0 else 'restituzione',
                'giacenza_id': giacenza_id,
                'prodotto_nome': giacenza_originale['nome_prodotto'],
                'giacenze_disponibili': [
                    {
                        'id': g['id'],
                        'ubicazione': g['ubicazione'] or 'Senza ubicazione',
                        'quantita': g['quantita'],
                        'magazzino': g['magazzino_nome']
                    } for g in giacenze_magazzino
                ],
                'form_data': {
                    'ubicazione': ubicazione,
                    'stato': stato,
                    'quantita': quantita_nuova,
                    'note': note
                }
            })
        
        # Aggiorna la giacenza direttamente (tutti gli altri casi)
        cursor.execute("""
            UPDATE giacenze 
            SET ubicazione = %s, stato = %s, quantita = %s, note = %s 
            WHERE id = %s
        """, (ubicazione, stato, quantita_nuova, note, giacenza_id))
        
        # Log del movimento di modifica
        cursor.execute("""
            INSERT INTO movimenti (prodotto_id, quantita, note, user_id, stato, a_ubicazione, a_magazzino_id, tipo_movimento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            giacenza_originale['prodotto_id'],
            quantita_nuova,
            f"Modifica giacenza: {note}",
            session.get('user_id'),
            stato,
            ubicazione,
            giacenza_originale['magazzino_id'],
            'MODIFICA'
        ))
        
        conn.commit()
        flash('Giacenza modificata con successo.', 'success')
        
        # Controlla soglie dopo la modifica
        check_and_create_notifications()
        
    except Exception as e:
        flash(f'Errore durante la modifica: {e}', 'error')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('index'))

@app.route('/conferma_modifica_giacenza', methods=['POST'])
def conferma_modifica_giacenza():
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        data = request.get_json()
        giacenza_id = data['giacenza_id']
        giacenza_compensazione_id = data['giacenza_compensazione_id']
        form_data = data['form_data']
        differenza = data['differenza']
        
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera giacenza originale
        cursor.execute("SELECT * FROM giacenze WHERE id = %s", (giacenza_id,))
        giacenza_originale = cursor.fetchone()
        
        if not giacenza_originale:
            return jsonify({'error': 'Giacenza originale non trovata'}), 400
        
        # Gestione ubicazione di compensazione
        if giacenza_compensazione_id == -1:  # Nuova ubicazione
            # Per le restituzioni (differenza < 0), creiamo una nuova giacenza
            if differenza >= 0:
                return jsonify({'error': 'Nuova ubicazione disponibile solo per restituzioni'}), 400
            
            # Recupera informazioni ubicazione dalle opzioni selezionate
            # In questo caso, l'ubicazione è specificata nei dati del frontend
            ubicazione_destinazione = data.get('ubicazione_destinazione')
            if not ubicazione_destinazione:
                return jsonify({'error': 'Ubicazione destinazione richiesta per nuova ubicazione'}), 400
            
            giacenza_compensazione = None  # Nessuna giacenza esistente da modificare
            
        else:  # Ubicazione esistente
            # Recupera giacenza di compensazione esistente
            cursor.execute("SELECT * FROM giacenze WHERE id = %s", (giacenza_compensazione_id,))
            giacenza_compensazione = cursor.fetchone()
            
            if not giacenza_compensazione:
                return jsonify({'error': 'Giacenza di compensazione non trovata'}), 400
            
            # Verifica disponibilità per prelievi
            if differenza > 0 and giacenza_compensazione['quantita'] < differenza:
                return jsonify({'error': 'Quantità insufficiente nell\'ubicazione selezionata'}), 400
        
        # Aggiorna giacenza principale
        cursor.execute("""
            UPDATE giacenze 
            SET ubicazione = %s, stato = %s, quantita = %s, note = %s 
            WHERE id = %s
        """, (form_data['ubicazione'], form_data['stato'], form_data['quantita'], form_data['note'], giacenza_id))
        
        # Gestione compensazione
        if giacenza_compensazione_id == -1:  # Nuova ubicazione per restituzione
            # Crea nuova giacenza nell'ubicazione specificata
            ubicazione_destinazione = data.get('ubicazione_destinazione')
            cursor.execute("""
                INSERT INTO giacenze (prodotto_id, quantita, ubicazione, stato, magazzino_id, note)
                VALUES (%s, %s, %s, 'IN_MAGAZZINO', %s, %s)
            """, (
                giacenza_originale['prodotto_id'],
                abs(differenza),  # Quantità restituita (positiva)
                ubicazione_destinazione,
                giacenza_originale['magazzino_id'],
                f"Restituzione da modifica giacenza {giacenza_id}"
            ))
            
            # Log movimento
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, quantita, note, user_id, stato, a_ubicazione, a_magazzino_id, da_ubicazione, da_magazzino_id, tipo_movimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                giacenza_originale['prodotto_id'],
                abs(differenza),
                f"Restituzione modifica giacenza: da {form_data['ubicazione']} a {ubicazione_destinazione}",
                session.get('user_id'),
                'IN_MAGAZZINO',
                ubicazione_destinazione,
                giacenza_originale['magazzino_id'],
                form_data['ubicazione'],
                giacenza_originale['magazzino_id'],
                'MODIFICA'
            ))
            
        else:  # Ubicazione esistente
            # Aggiorna giacenza di compensazione esistente
            nuova_quantita_compensazione = giacenza_compensazione['quantita'] - differenza
            if nuova_quantita_compensazione <= 0:
                cursor.execute("DELETE FROM giacenze WHERE id = %s", (giacenza_compensazione_id,))
            else:
                cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s", 
                             (nuova_quantita_compensazione, giacenza_compensazione_id))
            
            # Log movimento
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, quantita, note, user_id, stato, a_ubicazione, a_magazzino_id, da_ubicazione, da_magazzino_id, tipo_movimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                giacenza_originale['prodotto_id'],
                abs(differenza),
                f"Compensazione modifica giacenza: da {giacenza_compensazione['ubicazione']} a {form_data['ubicazione']}",
                session.get('user_id'),
                form_data['stato'],
                form_data['ubicazione'],
                giacenza_originale['magazzino_id'],
                giacenza_compensazione['ubicazione'],
                giacenza_compensazione['magazzino_id'],
                'MODIFICA'
            ))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

@app.route('/changelogs', methods=['GET', 'POST'])
def changelogs():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Solo admin può aggiungere/modificare changelog
        if not session.get('is_admin', False):
            flash('Accesso negato: solo admin può gestire i changelog.', 'error')
            return redirect(url_for('changelogs'))
        
        versione = request.form.get('versione')
        data_rilascio = request.form.get('data_rilascio')
        descrizione = request.form.get('descrizione')
        changelog_id = request.form.get('changelog_id')

        if not versione or not data_rilascio or not descrizione:
            flash('Tutti i campi sono obbligatori.', 'error')
            return redirect(url_for('changelogs'))

        try:
            conn = connect_to_database()
            cursor = conn.cursor()
            
            if changelog_id:  # Modifica esistente
                cursor.execute("""
                    UPDATE changelogs 
                    SET versione = %s, data_rilascio = %s, descrizione = %s 
                    WHERE id = %s
                """, (versione, data_rilascio, descrizione, changelog_id))
                flash('Changelog aggiornato con successo.', 'success')
            else:  # Nuovo changelog
                cursor.execute("""
                    INSERT INTO changelogs (versione, data_rilascio, descrizione, user_id)
                    VALUES (%s, %s, %s, %s)
                """, (versione, data_rilascio, descrizione, session.get('user_id')))
                flash('Changelog aggiunto con successo.', 'success')
            
            conn.commit()
            
        except Exception as e:
            flash(f'Errore durante il salvataggio: {e}', 'error')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        
        return redirect(url_for('changelogs'))
    
    # GET - Recupera tutti i changelog
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.*, u.username 
            FROM changelogs c
            LEFT JOIN utenti u ON c.user_id = u.id
            ORDER BY c.data_rilascio DESC, c.id DESC
        """)
        changelogs = cursor.fetchall()
        
    except Exception as e:
        changelogs = []
        flash(f'Errore nel recupero dei changelog: {e}', 'error')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return render_template('changelogs.html', changelogs=changelogs, username=session.get('username'))

@app.route('/delete_changelog/<int:changelog_id>', methods=['POST'])
def delete_changelog(changelog_id):
    if 'user_id' not in session or not session.get('is_admin', False):
        flash('Accesso negato: solo admin può eliminare i changelog.', 'error')
        return redirect(url_for('changelogs'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM changelogs WHERE id = %s", (changelog_id,))
        conn.commit()
        flash('Changelog eliminato con successo.', 'success')
        
    except Exception as e:
        flash(f'Errore durante l\'eliminazione: {e}', 'error')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return redirect(url_for('changelogs'))

# ---------------------------------------------------
# Route: Admin Panel
# ---------------------------------------------------
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if not session.get('is_admin', False):
        flash('Accesso negato: solo amministratori.', 'error')
        return redirect(url_for('index'))
    
    # Statistiche per il pannello admin
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Conta utenti totali
        cursor.execute("SELECT COUNT(*) as total FROM utenti")
        total_users = cursor.fetchone()['total']
        
        # Conta admin
        cursor.execute("SELECT COUNT(*) as total FROM utenti WHERE is_admin = TRUE")
        total_admins = cursor.fetchone()['total']
        
        # Conta notifiche inviate oggi (broadcast iniziano con [])
        cursor.execute("""
            SELECT COUNT(DISTINCT id) as total FROM notifications 
            WHERE DATE(data_notifica) = CURDATE() AND codice_prodotto LIKE '[%'
        """)
        notifications_today = cursor.fetchone()['total']
        
        # Ultimi broadcast (notifiche con [TIPO] nel codice_prodotto)
        cursor.execute("""
            SELECT codice_prodotto as riferimento, 
                   nome_prodotto as messaggio,
                   data_notifica,
                   CASE 
                     WHEN magazzino = 'info' THEN 'info'
                     WHEN magazzino = 'success' THEN 'success'
                     WHEN magazzino = 'warning' THEN 'warning'
                     WHEN magazzino = 'error' THEN 'error'
                     ELSE 'info'
                   END as tipo
            FROM notifications
            WHERE codice_prodotto LIKE '[%'
            ORDER BY data_notifica DESC
            LIMIT 5
        """)
        recent_broadcasts = cursor.fetchall()
        
    except Exception as e:
        flash(f'Errore nel caricamento statistiche: {e}', 'error')
        total_users = total_admins = notifications_today = 0
        recent_broadcasts = []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return render_template('admin_panel.html',
                         total_users=total_users,
                         total_admins=total_admins,
                         notifications_today=notifications_today,
                         recent_broadcasts=recent_broadcasts,
                         username=session.get('username'))

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if not session.get('is_admin', False):
        flash('Accesso negato: solo amministratori.', 'error')
        return redirect(url_for('index'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Ottieni tutti gli utenti
        cursor.execute("""
            SELECT id, username, email, is_admin, data_creazione 
            FROM utenti 
            ORDER BY data_creazione DESC
        """)
        users = cursor.fetchall()
        
    except Exception as e:
        flash(f'Errore nel caricamento utenti: {e}', 'error')
        users = []
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return render_template('admin_users.html', users=users, username=session.get('username'))

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    if 'user_id' not in session or not session.get('is_admin', False):
        return jsonify({'success': False, 'message': 'Accesso negato'}), 403
    
    titolo = request.form.get('titolo', '').strip()
    messaggio = request.form.get('messaggio', '').strip()
    tipo = request.form.get('tipo', 'info')  # info, warning, success, error
    
    if not titolo or not messaggio:
        return jsonify({'success': False, 'message': 'Titolo e messaggio sono obbligatori'}), 400
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        # Ottieni tutti gli utenti
        cursor.execute("SELECT id FROM utenti")
        users = cursor.fetchall()
        
        if not users:
            return jsonify({'success': False, 'message': 'Nessun utente trovato'}), 400
        
        # Crea notifica per ogni utente usando i campi esistenti
        # Uso nome_prodotto per il messaggio e codice_prodotto per il titolo
        for user in users:
            cursor.execute("""
                INSERT INTO notifications 
                (user_id, codice_prodotto, nome_prodotto, quantita_attuale, soglia_minima, magazzino, visualizzata)
                VALUES (%s, %s, %s, 0, 0, %s, FALSE)
            """, (user[0], f'[{tipo.upper()}] {titolo}', messaggio, tipo))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Notifica inviata a {len(users)} utenti'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore: {str(e)}'}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# ---------------------------------------------------
# Route: Rientro Merce
# ---------------------------------------------------
@app.route('/rientro_merce', methods=['GET', 'POST'])
def rientro_merce():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        giacenza_id = request.form.get('giacenza_id')
        prodotto_id = request.form.get('prodotto_id')
        target_ubicazione = request.form.get('target_ubicazione')
        quantita_da_rientrare = request.form.get('quantita_da_rientrare')
        note = (request.form.get('note') or '').strip() or None

        if not all([giacenza_id, prodotto_id, target_ubicazione, quantita_da_rientrare]):
            flash('Dati incompleti per il rientro.', 'error')
            return redirect(url_for('rientro_merce'))
        try:
            quantita_da_rientrare = int(quantita_da_rientrare)
            if quantita_da_rientrare <= 0:
                raise ValueError
        except ValueError:
            flash('Quantità non valida.', 'error')
            return redirect(url_for('rientro_merce'))

        try:
            conn = connect_to_database()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT g.*, p.nome_prodotto, p.codice_prodotto
                FROM giacenze g
                JOIN prodotti p ON g.prodotto_id = p.id
                WHERE g.id = %s
            """, (giacenza_id,))
            sorgente = cursor.fetchone()
            if not sorgente:
                flash('Giacenza di origine non trovata.', 'error')
                return redirect(url_for('rientro_merce'))
            if sorgente['prodotto_id'] != int(prodotto_id):
                flash('Mismatch prodotto/giacenza.', 'error')
                return redirect(url_for('rientro_merce'))
            if sorgente['quantita'] < quantita_da_rientrare:
                flash('Quantità richiesta superiore alla disponibilità fuori magazzino.', 'error')
                return redirect(url_for('rientro_merce'))

            cursor.execute("""
                SELECT * FROM giacenze
                WHERE prodotto_id = %s AND ubicazione = %s AND stato = 'in_magazzino'
            """, (prodotto_id, target_ubicazione))
            destinazione = cursor.fetchone()
            
            nuova_q_sorgente = sorgente['quantita'] - quantita_da_rientrare
            cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s", (nuova_q_sorgente, sorgente['id']))
            
            if destinazione:
                # Ubicazione esistente: aggiorna la quantità
                cursor.execute("""
                    UPDATE giacenze SET quantita = quantita + %s WHERE id = %s
                """, (quantita_da_rientrare, destinazione['id']))
            else:
                # Nuova ubicazione: crea un nuovo record
                cursor.execute("""
                    INSERT INTO giacenze (prodotto_id, quantita, ubicazione, stato, magazzino_id)
                    VALUES (%s, %s, %s, 'in_magazzino', %s)
                """, (prodotto_id, quantita_da_rientrare, target_ubicazione, 1))
                # Recupera l'ID della nuova giacenza creata
                cursor.execute("SELECT LAST_INSERT_ID() as new_id")
                destinazione = {'id': cursor.fetchone()['new_id'], 'ubicazione': target_ubicazione, 'magazzino_id': 1}
            
            if nuova_q_sorgente == 0:
                cursor.execute("DELETE FROM giacenze WHERE id = %s", (sorgente['id'],))

            cursor.execute("""
                INSERT INTO movimenti (
                    prodotto_id, quantita, note, user_id, stato,
                    a_ubicazione, a_magazzino_id, da_ubicazione, da_magazzino_id, tipo_movimento
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                sorgente['prodotto_id'],
                quantita_da_rientrare,
                note or f"Rientro da stato {sorgente['stato']} verso {target_ubicazione}",
                session.get('user_id'),
                'rientro',
                destinazione['ubicazione'],
                destinazione.get('magazzino_id'),
                sorgente.get('ubicazione'),
                sorgente.get('magazzino_id'),
                'TRASFERIMENTO'
            ))
            conn.commit()
            flash('Rientro effettuato con successo.', 'success')
        except Exception as e:
            if 'conn' in locals():
                conn.rollback()
            flash(f'Errore durante il rientro: {e}', 'error')
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        return redirect(url_for('rientro_merce'))

    # GET
    giacenze_fuori = []
    ubicazioni_per_prodotto = {}
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT g.id, g.prodotto_id, g.quantita, g.ubicazione AS ubicazione_fuori, g.stato,
                   p.nome_prodotto, p.codice_prodotto, g.note
            FROM giacenze g
            JOIN prodotti p ON g.prodotto_id = p.id
            WHERE g.stato <> 'in_magazzino'
            ORDER BY p.nome_prodotto ASC
        """)
        giacenze_fuori = cursor.fetchall()
        if giacenze_fuori:
            prodotto_ids = tuple({g['prodotto_id'] for g in giacenze_fuori})
            placeholder = ','.join(['%s'] * len(prodotto_ids))
            cursor.execute(f"""
                SELECT id, prodotto_id, ubicazione, quantita, stato, magazzino_id
                FROM giacenze
                WHERE prodotto_id IN ({placeholder}) AND stato = 'in_magazzino'
            """, prodotto_ids)
            rows = cursor.fetchall()
            for r in rows:
                ubicazioni_per_prodotto.setdefault(r['prodotto_id'], []).append(r)
    except Exception as e:
        flash(f'Errore recupero dati: {e}', 'error')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    return render_template('rientro_merce.html', giacenze_fuori=giacenze_fuori, ubicazioni_per_prodotto=ubicazioni_per_prodotto, username=session.get('username'))

# Route per pagina riconciliazione magazzino
@app.route('/warehouse-reconciliation')
def warehouse_reconciliation():
    """Mostra la pagina di riconciliazione magazzino."""
    return render_template('warehouse_reconciliation.html', username=session.get('username'))

#Route per verifica e confronto giacenze magazzino
@app.route('/api/reconcile-warehouse', methods=['POST'])
def reconcile_warehouse():
    """
    Endpoint principale per riconciliazione magazzino.
    
    Nuovo flusso semplificato:
    - Richiede solo i file AS400 (Magazzino 27 e/o 28)
    - I dati WebApp vengono caricati automaticamente dal database
    """
    try:
        # Raccolta file AS400
        magazzino_27 = request.files.get('magazzino_27')
        magazzino_28 = request.files.get('magazzino_28')

        # Validazione: almeno un file AS400 richiesto
        if not magazzino_27 and not magazzino_28:
            return jsonify({
                'success': False,
                'error': 'Almeno un file AS400 è richiesto (Magazzino 27 o 28)'
            }), 400

        # Reset posizione file
        if magazzino_27:
            magazzino_27.seek(0)
        if magazzino_28:
            magazzino_28.seek(0)

        # Importa e usa il nuovo processore con database
        from magazzino_reconciliation import process_as400_files_with_database, get_webapp_api_response
        
        report = process_as400_files_with_database(
            as400_mag27_file=magazzino_27,
            as400_mag28_file=magazzino_28
        )

        response = get_webapp_api_response(report)
        status_code = 200 if response['success'] else 500

        return jsonify(response), status_code

    except Exception as e:
        # Log dell'errore
        print(f"Errore riconciliazione: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# Route di debug per AS400
@app.route('/api/debug-as400-format', methods=['POST'])
def debug_as400_format():
    """Debug del formato file AS400."""
    try:
        file = request.files.get('as400_file')
        if not file:
            return jsonify({'error': 'Nessun file caricato'}), 400
        
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        from magazzino_reconciliation import MagazzinoReconciliation
        reconciler = MagazzinoReconciliation()
        debug_info = reconciler.debug_as400_format(content)
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health_check():
    """Health check."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.errorhandler(413)
def too_large(e):
    """File troppo grande."""
    return jsonify({
        'success': False,
        'error': 'File troppo grande (max 50MB)'
    }), 413



# Route per aggiornamento rapido quantità mobile
@app.route('/aggiorna_giacenza_rapida/<int:giacenza_id>', methods=['POST'])
def aggiorna_giacenza_rapida(giacenza_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
    
    try:
        data = request.get_json()
        nuova_quantita = int(data.get('quantita', 0))
        
        if nuova_quantita < 0:
            return jsonify({'success': False, 'error': 'Quantità non valida'}), 400
        
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Recupera i dati attuali della giacenza
        cursor.execute("""
            SELECT g.*, p.codice_prodotto, p.nome_prodotto 
            FROM giacenze g 
            JOIN prodotti p ON g.prodotto_id = p.id 
            WHERE g.id = %s
        """, (giacenza_id,))
        
        giacenza = cursor.fetchone()
        if not giacenza:
            return jsonify({'success': False, 'error': 'Giacenza non trovata'}), 404
        
        quantita_originale = giacenza['quantita']
        
        # Aggiorna la quantità
        cursor.execute("""
            UPDATE giacenze 
            SET quantita = %s 
            WHERE id = %s
        """, (nuova_quantita, giacenza_id))
        
        # Registra il movimento se la quantità è cambiata
        if nuova_quantita != quantita_originale:
            differenza = nuova_quantita - quantita_originale
            tipo_movimento = 'carico' if differenza > 0 else 'scarico'
            quantita_movimento = abs(differenza)
            
            cursor.execute("""
                INSERT INTO movimenti (prodotto_id, quantita, note, user_id, stato, a_ubicazione, a_magazzino_id, tipo_movimento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                giacenza['prodotto_id'],
                quantita_movimento,
                f"Modifica rapida mobile: {quantita_originale} → {nuova_quantita} ({'carico' if differenza > 0 else 'scarico'})",
                session.get('user_id'),
                'IN_MAGAZZINO',
                giacenza['ubicazione'],
                giacenza.get('magazzino_id', 1),
                'MODIFICA'
            ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quantità aggiornata con successo',
            'nuova_quantita': nuova_quantita
        })
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# --- DA INSERIRE IN TUTTI I TEMPLATE PRINCIPALI ---
# {% with messages = get_flashed_messages(with_categories=true) %}
#   {% if messages %}
#     <div class="w-full max-w-2xl mx-auto mt-4">
#       {% for category, message in messages %}
#         <div class="px-4 py-2 rounded text-sm mb-2
#           {% if category == 'success' %}bg-green-100 text-green-800
#           {% elif category == 'error' or category == 'danger' %}bg-red-100 text-red-800
#           {% else %}bg-gray-100 text-gray-800{% endif %}">
#           {{ message }}
#         </div>
#       {% endfor %}
#     </div>
#   {% endif %}
# {% endwith %}
# ---------------------------------------------------


# ========================================
# MOVIMENTO MULTIPLO (BATCH) - BETA
# ========================================

@app.route('/movimento-multiplo')
def movimento_multiplo():
    """Pagina Movimento Multiplo (Beta)"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Usa la lista statica degli stati
        stati = STATI_DISPONIBILI.copy()
        
        # Carica prodotti per autocomplete
        cursor.execute("SELECT id, nome_prodotto, codice_prodotto FROM prodotti ORDER BY nome_prodotto")
        prodotti = cursor.fetchall()
        
    except Error as e:
        flash(f"Errore nel caricamento dati: {e}", "error")
        stati = STATI_DISPONIBILI.copy()
        prodotti = []
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
    
    return render_template('movimento_multiplo.html', stati=stati, prodotti=prodotti)


@app.route('/api/movimento-multiplo/execute', methods=['POST'])
def movimento_multiplo_execute():
    """Esegue i movimenti batch in una singola transazione"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Non autenticato'}), 401
    
    data = request.get_json()
    if not data or 'movimenti' not in data or len(data['movimenti']) == 0:
        return jsonify({'success': False, 'error': 'Nessun movimento da elaborare'})
    
    stato_origine = data.get('stato_origine_globale')
    movimenti = data['movimenti']
    user_id = session.get('user_id')
    
    conn = None
    cursor = None
    
    try:
        conn = connect_to_database()
        conn.autocommit = False  # Disabilita autocommit esplicitamente
        cursor = conn.cursor(dictionary=True, buffered=True)
        
        # Fase 1: Validazione di tutti i movimenti
        errori_validazione = []
        for i, mov in enumerate(movimenti):
            prodotto_id = mov.get('prodotto_id')
            da_ubicazione = mov.get('da_ubicazione')
            quantita = mov.get('quantita', 0)
            
            if not prodotto_id:
                errori_validazione.append(f'Movimento {i+1}: prodotto mancante')
                continue
            
            if quantita <= 0:
                errori_validazione.append(f'Movimento {i+1}: quantità non valida')
                continue
            
            # Verifica giacenza disponibile
            cursor.execute("""
                SELECT quantita FROM giacenze 
                WHERE prodotto_id = %s AND stato = %s AND ubicazione = %s
            """, (prodotto_id, stato_origine, da_ubicazione))
            giacenza = cursor.fetchone()
            
            if not giacenza:
                errori_validazione.append(f'Movimento {i+1}: giacenza non trovata per ubicazione {da_ubicazione}')
                continue
            
            if giacenza['quantita'] < quantita:
                errori_validazione.append(f'Movimento {i+1}: giacenza insufficiente (disponibili: {giacenza["quantita"]}, richiesti: {quantita})')
        
        # Se ci sono errori di validazione, esci
        if errori_validazione:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': errori_validazione[0]})
        
        # Fase 2: Esecuzione movimenti
        for mov in movimenti:
            prodotto_id = mov.get('prodotto_id')
            da_ubicazione = mov.get('da_ubicazione')
            a_ubicazione = mov.get('a_ubicazione')
            quantita = mov.get('quantita')
            nota = mov.get('nota', '')
            stato_dest = mov.get('stato_destinazione')
            
            # Determina magazzino_id (default)
            cursor.execute("SELECT magazzino_id FROM giacenze WHERE prodotto_id = %s LIMIT 1", (prodotto_id,))
            mag_result = cursor.fetchone()
            magazzino_id = mag_result['magazzino_id'] if mag_result else None
            
            # Tipo movimento: sempre TRASFERIMENTO per movimento multiplo
            # SCARICO e CARICO sono riservati alle rispettive pagine dedicate
            tipo_mov = 'TRASFERIMENTO'
            
            # 1. Inserisci record movimento
            cursor.execute("""
                INSERT INTO movimenti (
                    prodotto_id, da_magazzino_id, a_magazzino_id, 
                    da_ubicazione, a_ubicazione, quantita, note, 
                    user_id, stato, tipo_movimento
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (prodotto_id, magazzino_id, magazzino_id, da_ubicazione, a_ubicazione, quantita, nota, user_id, stato_dest, tipo_mov))
            
            # 2. Decrementa giacenza origine
            cursor.execute("""
                SELECT id, quantita FROM giacenze 
                WHERE prodotto_id = %s AND stato = %s AND ubicazione = %s
            """, (prodotto_id, stato_origine, da_ubicazione))
            giacenza_origine = cursor.fetchone()
            
            nuova_qty_origine = giacenza_origine['quantita'] - quantita
            if nuova_qty_origine <= 0:
                cursor.execute("DELETE FROM giacenze WHERE id = %s", (giacenza_origine['id'],))
            else:
                cursor.execute("UPDATE giacenze SET quantita = %s WHERE id = %s", (nuova_qty_origine, giacenza_origine['id']))
            
            # 3. Incrementa/crea giacenza destinazione
            # Cerca giacenza esistente con stesso prodotto, stato, ubicazione E nota
            cursor.execute("""
                SELECT id, quantita FROM giacenze 
                WHERE prodotto_id = %s AND stato = %s 
                AND (ubicazione = %s OR (ubicazione IS NULL AND %s IS NULL))
                AND (note = %s OR (note IS NULL AND %s IS NULL) OR (note = '' AND %s = ''))
            """, (prodotto_id, stato_dest, a_ubicazione, a_ubicazione, nota, nota, nota))
            giacenza_dest = cursor.fetchone()
            
            if giacenza_dest:
                cursor.execute("UPDATE giacenze SET quantita = quantita + %s WHERE id = %s", (quantita, giacenza_dest['id']))
            else:
                cursor.execute("""
                    INSERT INTO giacenze (prodotto_id, magazzino_id, ubicazione, stato, quantita, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (prodotto_id, magazzino_id, a_ubicazione, stato_dest, quantita, nota))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': f'{len(movimenti)} movimenti eseguiti con successo!'
        })
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass


@app.route('/api/movimento-multiplo/bozza', methods=['POST'])
def movimento_multiplo_salva_bozza():
    """Salva una bozza di movimento multiplo"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Non autenticato'}), 401
    
    data = request.get_json()
    user_id = session.get('user_id')
    
    nome_bozza = data.get('nome_bozza', '').strip()
    if not nome_bozza:
        return jsonify({'success': False, 'error': 'Nome bozza obbligatorio'})
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Conta bozze esistenti per l'utente
        cursor.execute("SELECT COUNT(*) as count FROM movimenti_batch_draft WHERE user_id = %s", (user_id,))
        count = cursor.fetchone()['count']
        
        # Se già 10 bozze, elimina la più vecchia
        if count >= 10:
            cursor.execute("""
                DELETE FROM movimenti_batch_draft 
                WHERE user_id = %s 
                ORDER BY created_at ASC 
                LIMIT 1
            """, (user_id,))
        
        # Salva nuova bozza
        json_items = json.dumps(data.get('movimenti', []))
        cursor.execute("""
            INSERT INTO movimenti_batch_draft (user_id, nome_bozza, json_items, nota_globale, stato_origine, stato_destinazione)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, nome_bozza, json_items, data.get('nota_globale', ''), data.get('stato_origine', ''), data.get('stato_destinazione', '')))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/movimento-multiplo/bozze')
def movimento_multiplo_lista_bozze():
    """Lista bozze dell'utente"""
    if 'user_id' not in session:
        return jsonify([])
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT id, nome_bozza, created_at 
            FROM movimenti_batch_draft 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (session.get('user_id'),))
        
        bozze = cursor.fetchall()
        
        # Converti datetime in string
        for b in bozze:
            if b['created_at']:
                b['created_at'] = b['created_at'].isoformat()
        
        return jsonify(bozze)
        
    except Exception as e:
        return jsonify([])
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/movimento-multiplo/bozza/<int:bozza_id>')
def movimento_multiplo_carica_bozza(bozza_id):
    """Carica una bozza specifica"""
    if 'user_id' not in session:
        return jsonify({'error': 'Non autenticato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT * FROM movimenti_batch_draft 
            WHERE id = %s AND user_id = %s
        """, (bozza_id, session.get('user_id')))
        
        bozza = cursor.fetchone()
        
        if not bozza:
            return jsonify({'error': 'Bozza non trovata'}), 404
        
        return jsonify({
            'stato_origine': bozza['stato_origine'],
            'stato_destinazione': bozza['stato_destinazione'],
            'nota_globale': bozza['nota_globale'],
            'movimenti': json.loads(bozza['json_items']) if bozza['json_items'] else []
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/movimento-multiplo/bozza/<int:bozza_id>', methods=['DELETE'])
def movimento_multiplo_elimina_bozza(bozza_id):
    """Elimina una bozza"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Non autenticato'}), 401
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM movimenti_batch_draft 
            WHERE id = %s AND user_id = %s
        """, (bozza_id, session.get('user_id')))
        
        conn.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


# ========================================
# NOTE: Le routes delle STATISTICHE sono state
# spostate in routes/statistics.py (stats_bp blueprint)
# Include: /statistiche, /api/statistiche/*
# ========================================


if __name__ == '__main__':
    # Debug: stampa la mappa delle rotte registrate
    print('--- URL MAP ---')
    print(app.url_map)
    print('---------------')
    # Usa configurazione/env invece di hardcoded port 80
    debug_flag = app.config.get('DEBUG', False)
    port = int(os.getenv('PORT', '5000'))
    host = os.getenv('HOST', '0.0.0.0')
    app.run(debug=debug_flag, host=host, port=port)
