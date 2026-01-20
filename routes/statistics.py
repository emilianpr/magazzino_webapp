# routes/statistics.py
# Blueprint per le rotte delle statistiche

from flask import Blueprint, render_template, request, jsonify, session, make_response
from datetime import datetime, timedelta
import io

from database_connection import connect_to_database
from utils.decorators import login_required, api_login_required
from utils.cache import get_stats_cache_key, get_cached_stats, set_cached_stats

stats_bp = Blueprint('statistics', __name__)


# ============================================================
# FUNZIONI HELPER PER LE STATISTICHE
# ============================================================

def get_date_range_from_param(range_param):
    """Converte un parametro range (es. '7d', '30d', '6m', '1y') in date start/end"""
    today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    if range_param == '7d':
        start_date = today - timedelta(days=7)
    elif range_param == '30d':
        start_date = today - timedelta(days=30)
    elif range_param == '90d':
        start_date = today - timedelta(days=90)
    elif range_param == '6m':
        start_date = today - timedelta(days=180)
    elif range_param == '1y':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=30)
    
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_date, today


def get_previous_period_range(start_date, end_date):
    """Calcola il periodo precedente equivalente per confronti"""
    delta = end_date - start_date
    prev_end = start_date - timedelta(seconds=1)
    prev_start = prev_end - delta
    return prev_start, prev_end


# ============================================================
# PAGINA PRINCIPALE STATISTICHE
# ============================================================

@stats_bp.route('/statistiche')
@login_required
def statistiche():
    """Pagina principale delle statistiche"""
    return render_template('statistiche.html', active_page='statistiche')


# ============================================================
# API STATISTICHE
# ============================================================

@stats_bp.route('/api/statistiche')
@api_login_required
def api_statistiche():
    """API principale statistiche con KPI e metriche"""
    range_param = request.args.get('range', '30d')
    
    # Check cache
    cache_key = get_stats_cache_key('stats_main', range_param)
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    prev_start, prev_end = get_previous_period_range(start_date, end_date)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Movimenti periodo corrente
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as totale_carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as totale_scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as totale_trasferimenti,
                COUNT(DISTINCT prodotto_id) as prodotti_movimentati
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (start_date, end_date))
        current = cursor.fetchone()
        
        # Movimenti periodo precedente (per calcolo delta)
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as totale_carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as totale_scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as totale_trasferimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (prev_start, prev_end))
        previous = cursor.fetchone()
        
        # Giacenze attuali totali
        cursor.execute("""
            SELECT 
                SUM(quantita) as totale_giacenze,
                COUNT(DISTINCT prodotto_id) as prodotti_in_stock
            FROM giacenze
            WHERE quantita > 0
        """)
        giacenze = cursor.fetchone()
        
        # Prodotti sotto soglia
        cursor.execute("""
            SELECT COUNT(*) as sotto_soglia
            FROM (
                SELECT p.id, COALESCE(SUM(g.quantita), 0) as qta_totale, pt.soglia_minima
                FROM prodotti p
                LEFT JOIN giacenze g ON p.id = g.prodotto_id
                LEFT JOIN product_thresholds pt ON p.codice_prodotto COLLATE utf8mb4_unicode_ci = pt.codice_prodotto
                WHERE pt.soglia_minima IS NOT NULL AND pt.notifica_attiva = 1
                GROUP BY p.id, pt.soglia_minima
                HAVING qta_totale < pt.soglia_minima
            ) as sottosoglia
        """)
        soglia_result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Calcola delta percentuali
        def calc_delta(current_val, prev_val):
            c = current_val or 0
            p = prev_val or 0
            if p == 0:
                return 100 if c > 0 else 0
            return round(((c - p) / p) * 100, 1)
        
        result = {
            'periodo': {
                'range': range_param,
                'inizio': start_date.strftime('%d/%m/%Y'),
                'fine': end_date.strftime('%d/%m/%Y')
            },
            'kpi': {
                'totale_movimenti': current['totale_movimenti'] or 0,
                'delta_movimenti': calc_delta(current['totale_movimenti'], previous['totale_movimenti']),
                'totale_carichi': int(current['totale_carichi'] or 0),
                'delta_carichi': calc_delta(current['totale_carichi'], previous['totale_carichi']),
                'totale_scarichi': int(current['totale_scarichi'] or 0),
                'delta_scarichi': calc_delta(current['totale_scarichi'], previous['totale_scarichi']),
                'totale_trasferimenti': int(current['totale_trasferimenti'] or 0),
                'delta_trasferimenti': calc_delta(current['totale_trasferimenti'], previous['totale_trasferimenti']),
                'prodotti_movimentati': current['prodotti_movimentati'] or 0,
                'giacenze_totali': int(giacenze['totale_giacenze'] or 0),
                'prodotti_in_stock': giacenze['prodotti_in_stock'] or 0,
                'prodotti_sotto_soglia': soglia_result['sotto_soglia'] or 0
            }
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/trend')
@api_login_required
def api_statistiche_trend():
    """API per i dati del grafico trend (movimenti nel tempo)"""
    range_param = request.args.get('range', '30d')
    
    cache_key = get_stats_cache_key('stats_trend', range_param)
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    
    # Determina granularità in base al range
    if range_param in ['7d']:
        group_by = 'DATE(data_ora)'
        date_format = '%d/%m'
    elif range_param in ['30d', '90d']:
        group_by = 'DATE(data_ora)'
        date_format = '%d/%m'
    else:
        group_by = "DATE_FORMAT(data_ora, '%Y-%m')"
        date_format = '%m/%Y'
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(f"""
            SELECT 
                {group_by} as periodo,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as trasferimenti,
                COUNT(*) as num_movimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY {group_by}
            ORDER BY periodo ASC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        labels = []
        carichi = []
        scarichi = []
        trasferimenti = []
        
        for row in rows:
            periodo = row['periodo']
            if isinstance(periodo, datetime):
                labels.append(periodo.strftime(date_format))
            else:
                labels.append(str(periodo))
            carichi.append(int(row['carichi'] or 0))
            scarichi.append(int(row['scarichi'] or 0))
            trasferimenti.append(int(row['trasferimenti'] or 0))
        
        result = {
            'labels': labels,
            'datasets': {
                'carichi': carichi,
                'scarichi': scarichi,
                'trasferimenti': trasferimenti
            }
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/per-stato')
@api_login_required
def api_statistiche_per_stato():
    """API per distribuzione giacenze per stato"""
    cache_key = get_stats_cache_key('stats_stato', 'current')
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT stato, SUM(quantita) as totale
            FROM giacenze
            WHERE quantita > 0
            GROUP BY stato
            ORDER BY totale DESC
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = {
            'labels': [row['stato'].replace('_', ' ').title() for row in rows],
            'data': [int(row['totale']) for row in rows],
            'raw_labels': [row['stato'] for row in rows]
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/utenti')
@api_login_required
def api_statistiche_utenti():
    """API per statistiche breakdown per utente"""
    range_param = request.args.get('range', '30d')
    
    cache_key = get_stats_cache_key('stats_utenti', range_param)
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                u.username,
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN m.tipo_movimento = 'CARICO' THEN m.quantita ELSE 0 END) as carichi,
                SUM(CASE WHEN m.tipo_movimento = 'SCARICO' THEN m.quantita ELSE 0 END) as scarichi,
                SUM(CASE WHEN m.tipo_movimento = 'TRASFERIMENTO' THEN m.quantita ELSE 0 END) as trasferimenti
            FROM movimenti m
            JOIN utenti u ON m.user_id = u.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY m.user_id, u.username
            ORDER BY totale_movimenti DESC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = {
            'utenti': [{
                'username': row['username'],
                'totale_movimenti': row['totale_movimenti'],
                'carichi': int(row['carichi'] or 0),
                'scarichi': int(row['scarichi'] or 0),
                'trasferimenti': int(row['trasferimenti'] or 0)
            } for row in rows]
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/top-prodotti')
@api_login_required
def api_statistiche_top_prodotti():
    """API per i prodotti più movimentati"""
    range_param = request.args.get('range', '30d')
    limit = min(int(request.args.get('limit', 10)), 50)
    
    cache_key = get_stats_cache_key('stats_top_prodotti', f"{range_param}_{limit}")
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                p.id,
                p.nome_prodotto as nome,
                p.codice_prodotto as codice,
                COUNT(*) as num_movimenti,
                SUM(m.quantita) as quantita_totale
            FROM movimenti m
            JOIN prodotti p ON m.prodotto_id = p.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY p.id, p.nome_prodotto, p.codice_prodotto
            ORDER BY num_movimenti DESC
            LIMIT %s
        """, (start_date, end_date, limit))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = {
            'prodotti': [{
                'id': row['id'],
                'nome': row['nome'],
                'codice': row['codice'],
                'num_movimenti': row['num_movimenti'],
                'quantita_totale': int(row['quantita_totale'] or 0)
            } for row in rows]
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/avanzate')
@api_login_required
def api_statistiche_avanzate():
    """API per statistiche avanzate: fasce orarie, giorni settimana, metriche extra"""
    range_param = request.args.get('range', '30d')
    
    cache_key = get_stats_cache_key('stats_avanzate', range_param)
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Distribuzione per fascia oraria
        cursor.execute("""
            SELECT 
                HOUR(data_ora) as ora,
                COUNT(*) as num_movimenti,
                SUM(quantita) as quantita_totale
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY HOUR(data_ora)
            ORDER BY ora
        """, (start_date, end_date))
        fasce_orarie_raw = cursor.fetchall()
        
        # Crea array completo delle 24 ore
        fasce_orarie = []
        fasce_dict = {row['ora']: row for row in fasce_orarie_raw}
        for ora in range(24):
            if ora in fasce_dict:
                fasce_orarie.append({
                    'ora': f"{ora:02d}:00",
                    'movimenti': fasce_dict[ora]['num_movimenti'],
                    'quantita': int(fasce_dict[ora]['quantita_totale'] or 0)
                })
            else:
                fasce_orarie.append({'ora': f"{ora:02d}:00", 'movimenti': 0, 'quantita': 0})
        
        # Distribuzione per giorno della settimana
        cursor.execute("""
            SELECT 
                DAYOFWEEK(data_ora) as giorno_num,
                DAYNAME(data_ora) as giorno_nome,
                COUNT(*) as num_movimenti,
                SUM(quantita) as quantita_totale
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY DAYOFWEEK(data_ora), DAYNAME(data_ora)
            ORDER BY giorno_num
        """, (start_date, end_date))
        giorni_settimana_raw = cursor.fetchall()
        
        # Mappa nomi italiani
        giorni_it = {
            'Sunday': 'Domenica', 'Monday': 'Lunedì', 'Tuesday': 'Martedì',
            'Wednesday': 'Mercoledì', 'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato'
        }
        giorni_settimana = [{
            'giorno': giorni_it.get(row['giorno_nome'], row['giorno_nome']),
            'movimenti': row['num_movimenti'],
            'quantita': int(row['quantita_totale'] or 0)
        } for row in giorni_settimana_raw]
        
        # Statistiche aggregate avanzate
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                COUNT(DISTINCT DATE(data_ora)) as giorni_attivi,
                COUNT(DISTINCT user_id) as utenti_attivi,
                MAX(quantita) as quantita_max_singola,
                MIN(quantita) as quantita_min_singola,
                AVG(quantita) as quantita_media,
                STDDEV(quantita) as quantita_stddev
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (start_date, end_date))
        metriche = cursor.fetchone()
        
        # Giorno con più movimenti
        cursor.execute("""
            SELECT 
                DATE(data_ora) as data,
                COUNT(*) as movimenti,
                SUM(quantita) as quantita
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY DATE(data_ora)
            ORDER BY movimenti DESC
            LIMIT 1
        """, (start_date, end_date))
        picco_giornaliero = cursor.fetchone()
        
        # Ora con più movimenti
        cursor.execute("""
            SELECT 
                HOUR(data_ora) as ora,
                COUNT(*) as movimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY HOUR(data_ora)
            ORDER BY movimenti DESC
            LIMIT 1
        """, (start_date, end_date))
        ora_piu_attiva = cursor.fetchone()
        
        # Movimenti per magazzino
        cursor.execute("""
            SELECT 
                COALESCE(mag.nome, 'Non specificato') as nome,
                COUNT(*) as num_movimenti,
                SUM(CASE WHEN m.tipo_movimento = 'CARICO' THEN m.quantita ELSE 0 END) as entrate,
                SUM(CASE WHEN m.tipo_movimento = 'SCARICO' THEN m.quantita ELSE 0 END) as uscite,
                SUM(CASE WHEN m.tipo_movimento = 'TRASFERIMENTO' THEN m.quantita ELSE 0 END) as trasferimenti
            FROM movimenti m
            LEFT JOIN magazzini mag ON m.a_magazzino_id = mag.id OR m.da_magazzino_id = mag.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY COALESCE(mag.nome, 'Non specificato')
            ORDER BY num_movimenti DESC
        """, (start_date, end_date))
        magazzini_raw = cursor.fetchall()
        
        totale_mag = sum(m['num_movimenti'] for m in magazzini_raw) or 1
        magazzini = [{
            'nome': m['nome'],
            'movimenti': m['num_movimenti'],
            'percentuale': round((m['num_movimenti'] / totale_mag) * 100, 1),
            'entrate': int(m['entrate'] or 0),
            'uscite': int(m['uscite'] or 0),
            'trasferimenti': int(m['trasferimenti'] or 0),
            'saldo': int((m['entrate'] or 0) - (m['uscite'] or 0))
        } for m in magazzini_raw]
        
        # Prodotti sotto soglia
        cursor.execute("""
            SELECT 
                p.codice_prodotto as codice,
                p.nome_prodotto as nome,
                COALESCE(SUM(g.quantita), 0) as giacenza,
                pt.soglia_minima as soglia,
                pt.soglia_minima - COALESCE(SUM(g.quantita), 0) as mancanti
            FROM product_thresholds pt
            JOIN prodotti p ON pt.codice_prodotto COLLATE utf8mb4_unicode_ci = p.codice_prodotto COLLATE utf8mb4_unicode_ci
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            WHERE pt.notifica_attiva = 1
            GROUP BY p.id, p.codice_prodotto, p.nome_prodotto, pt.soglia_minima
            HAVING giacenza < pt.soglia_minima
            ORDER BY mancanti DESC
            LIMIT 10
        """)
        sotto_soglia = cursor.fetchall()
        prodotti_sotto_soglia = [{
            'codice': p['codice'],
            'nome': p['nome'],
            'giacenza': int(p['giacenza']),
            'soglia': int(p['soglia']),
            'mancanti': int(p['mancanti'])
        } for p in sotto_soglia]
        
        cursor.close()
        conn.close()
        
        # Calcola giorni periodo
        giorni_periodo = (end_date - start_date).days or 1
        
        result = {
            'fasce_orarie': fasce_orarie,
            'giorni_settimana': giorni_settimana,
            'metriche_avanzate': {
                'giorni_totali_periodo': giorni_periodo,
                'giorni_attivi': metriche['giorni_attivi'] or 0,
                'giorni_inattivi': giorni_periodo - (metriche['giorni_attivi'] or 0),
                'utenti_attivi': metriche['utenti_attivi'] or 0,
                'media_movimenti_giorno': round((metriche['totale_movimenti'] or 0) / (metriche['giorni_attivi'] or 1), 1),
                'quantita_max_singola': int(metriche['quantita_max_singola'] or 0),
                'quantita_min_singola': int(metriche['quantita_min_singola'] or 0),
                'quantita_media': round(float(metriche['quantita_media'] or 0), 1),
                'quantita_deviazione_std': round(float(metriche['quantita_stddev'] or 0), 1),
                'picco_giornaliero': {
                    'data': picco_giornaliero['data'].strftime('%d/%m/%Y') if picco_giornaliero and picco_giornaliero['data'] else '-',
                    'movimenti': picco_giornaliero['movimenti'] if picco_giornaliero else 0,
                    'quantita': int(picco_giornaliero['quantita'] or 0) if picco_giornaliero else 0
                },
                'ora_piu_attiva': f"{ora_piu_attiva['ora']:02d}:00" if ora_piu_attiva else '-'
            },
            'magazzini': magazzini,
            'prodotti_sotto_soglia': prodotti_sotto_soglia
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/confronto-periodi')
@api_login_required
def api_statistiche_confronto_periodi():
    """API per dati del grafico di confronto con periodo precedente"""
    range_param = request.args.get('range', '30d')
    
    cache_key = get_stats_cache_key('stats_confronto', range_param)
    cached = get_cached_stats(cache_key)
    if cached:
        return jsonify(cached)
    
    start_date, end_date = get_date_range_from_param(range_param)
    prev_start, prev_end = get_previous_period_range(start_date, end_date)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Periodo corrente
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as trasferimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (start_date, end_date))
        corrente = cursor.fetchone()
        
        # Periodo precedente
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as trasferimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (prev_start, prev_end))
        precedente = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        result = {
            'periodo_corrente': {
                'label': f"{start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m/%Y')}",
                'movimenti': corrente['totale_movimenti'] or 0,
                'carichi': int(corrente['carichi'] or 0),
                'scarichi': int(corrente['scarichi'] or 0),
                'trasferimenti': int(corrente['trasferimenti'] or 0)
            },
            'periodo_precedente': {
                'label': f"{prev_start.strftime('%d/%m')} - {prev_end.strftime('%d/%m/%Y')}",
                'movimenti': precedente['totale_movimenti'] or 0,
                'carichi': int(precedente['carichi'] or 0),
                'scarichi': int(precedente['scarichi'] or 0),
                'trasferimenti': int(precedente['trasferimenti'] or 0)
            }
        }
        
        set_cached_stats(cache_key, result)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/export/csv')
@api_login_required
def api_statistiche_export_csv():
    """Export statistiche in formato CSV"""
    range_param = request.args.get('range', '30d')
    start_date, end_date = get_date_range_from_param(range_param)
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # Esporta movimenti del periodo
        cursor.execute("""
            SELECT 
                m.data_ora,
                m.tipo_movimento,
                p.nome_prodotto as prodotto,
                p.codice_prodotto as codice,
                m.quantita,
                m.stato,
                m.da_ubicazione,
                m.a_ubicazione,
                u.username,
                m.note
            FROM movimenti m
            JOIN prodotti p ON m.prodotto_id = p.id
            LEFT JOIN utenti u ON m.user_id = u.id
            WHERE m.data_ora BETWEEN %s AND %s
            ORDER BY m.data_ora DESC
        """, (start_date, end_date))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Genera CSV
        import csv
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Header
        writer.writerow([
            'Data/Ora', 'Tipo Movimento', 'Prodotto', 'Codice', 'Quantità',
            'Stato', 'Da Ubicazione', 'A Ubicazione', 'Utente', 'Note'
        ])
        
        for row in rows:
            writer.writerow([
                row['data_ora'].strftime('%d/%m/%Y %H:%M') if row['data_ora'] else '',
                row['tipo_movimento'],
                row['prodotto'],
                row['codice'],
                row['quantita'],
                row['stato'] or '',
                row['da_ubicazione'] or '',
                row['a_ubicazione'] or '',
                row['username'] or '',
                row['note'] or ''
            ])
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=statistiche_{range_param}_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stats_bp.route('/api/statistiche/export/pdf')
@api_login_required
def api_statistiche_export_pdf():
    """Export statistiche in formato PDF con grafici e dati dettagliati"""
    range_param = request.args.get('range', '30d')
    
    try:
        # Importa WeasyPrint e matplotlib
        from weasyprint import HTML, CSS
        import matplotlib
        matplotlib.use('Agg')  # Backend senza GUI
        import matplotlib.pyplot as plt
        import base64
        from flask import render_template as flask_render_template
        
        start_date, end_date = get_date_range_from_param(range_param)
        prev_start, prev_end = get_previous_period_range(start_date, end_date)
        
        # Calcola giorni nel periodo
        giorni_periodo = (end_date - start_date).days or 1
        
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        
        # KPI periodo corrente
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as totale_carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as totale_scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as totale_trasferimenti,
                COUNT(DISTINCT prodotto_id) as prodotti_movimentati,
                COUNT(DISTINCT DATE(data_ora)) as giorni_attivi,
                COUNT(DISTINCT user_id) as utenti_attivi
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (start_date, end_date))
        kpi_corrente = cursor.fetchone()
        
        # KPI periodo precedente per delta
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as totale_carichi,
                SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as totale_scarichi,
                SUM(CASE WHEN tipo_movimento = 'TRASFERIMENTO' THEN quantita ELSE 0 END) as totale_trasferimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (prev_start, prev_end))
        kpi_prev = cursor.fetchone()
        
        # Calcola delta percentuali
        def calc_delta(current, previous):
            if previous and previous > 0:
                return ((current - previous) / previous) * 100
            elif current > 0:
                return 100
            return 0
        
        totale_movimenti = kpi_corrente['totale_movimenti'] or 0
        totale_carichi = int(kpi_corrente['totale_carichi'] or 0)
        totale_scarichi = int(kpi_corrente['totale_scarichi'] or 0)
        totale_trasferimenti = int(kpi_corrente['totale_trasferimenti'] or 0)
        giorni_attivi = kpi_corrente['giorni_attivi'] or 0
        
        kpi = {
            'totale_movimenti': totale_movimenti,
            'totale_carichi': totale_carichi,
            'totale_scarichi': totale_scarichi,
            'totale_trasferimenti': totale_trasferimenti,
            'prodotti_movimentati': kpi_corrente['prodotti_movimentati'] or 0,
            'giorni_attivi': giorni_attivi,
            'utenti_attivi': kpi_corrente['utenti_attivi'] or 0,
            'media_giornaliera': totale_movimenti / giorni_attivi if giorni_attivi > 0 else 0,
            'delta_movimenti': calc_delta(totale_movimenti, kpi_prev['totale_movimenti'] or 0),
            'delta_carichi': calc_delta(totale_carichi, int(kpi_prev['totale_carichi'] or 0)),
            'delta_scarichi': calc_delta(totale_scarichi, int(kpi_prev['totale_scarichi'] or 0)),
            'delta_trasferimenti': calc_delta(totale_trasferimenti, int(kpi_prev['totale_trasferimenti'] or 0))
        }
        
        # Trend per grafico
        if range_param in ['6m', '1y']:
            # Raggruppa per mese per periodi lunghi
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(data_ora, '%%Y-%%m') as periodo,
                    SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as carichi,
                    SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as scarichi
                FROM movimenti
                WHERE data_ora BETWEEN %s AND %s
                GROUP BY DATE_FORMAT(data_ora, '%%Y-%%m')
                ORDER BY periodo
            """, (start_date, end_date))
        else:
            cursor.execute("""
                SELECT 
                    DATE(data_ora) as periodo,
                    SUM(CASE WHEN tipo_movimento = 'CARICO' THEN quantita ELSE 0 END) as carichi,
                    SUM(CASE WHEN tipo_movimento = 'SCARICO' THEN quantita ELSE 0 END) as scarichi
                FROM movimenti
                WHERE data_ora BETWEEN %s AND %s
                GROUP BY DATE(data_ora)
                ORDER BY periodo
            """, (start_date, end_date))
        trend_data = cursor.fetchall()
        
        # Top 10 prodotti con dettagli
        cursor.execute("""
            SELECT 
                p.codice_prodotto as codice,
                p.nome_prodotto as nome, 
                COUNT(*) as movimenti,
                SUM(m.quantita) as quantita
            FROM movimenti m
            JOIN prodotti p ON m.prodotto_id = p.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY p.id, p.codice_prodotto, p.nome_prodotto
            ORDER BY movimenti DESC
            LIMIT 10
        """, (start_date, end_date))
        top_prodotti_raw = cursor.fetchall()
        
        # Calcola percentuali per top prodotti
        totale_mov = sum(p['movimenti'] for p in top_prodotti_raw) or 1
        top_prodotti = []
        for p in top_prodotti_raw:
            top_prodotti.append({
                'codice': p['codice'],
                'nome': p['nome'],
                'movimenti': p['movimenti'],
                'quantita': int(p['quantita'] or 0),
                'percentuale': (p['movimenti'] / totale_mov) * 100
            })
        
        # Breakdown utenti con dettaglio per tipo
        cursor.execute("""
            SELECT 
                u.username,
                COUNT(*) as totale,
                SUM(CASE WHEN m.tipo_movimento = 'CARICO' THEN 1 ELSE 0 END) as carichi,
                SUM(CASE WHEN m.tipo_movimento = 'SCARICO' THEN 1 ELSE 0 END) as scarichi,
                SUM(CASE WHEN m.tipo_movimento = 'TRASFERIMENTO' THEN 1 ELSE 0 END) as trasferimenti
            FROM movimenti m
            JOIN utenti u ON m.user_id = u.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY u.id, u.username
            ORDER BY totale DESC
        """, (start_date, end_date))
        utenti_raw = cursor.fetchall()
        
        # Calcola percentuali per utenti
        totale_utenti_mov = sum(u['totale'] for u in utenti_raw) or 1
        utenti = []
        for u in utenti_raw:
            utenti.append({
                'username': u['username'],
                'totale': u['totale'],
                'carichi': u['carichi'],
                'scarichi': u['scarichi'],
                'trasferimenti': u['trasferimenti'],
                'percentuale': (u['totale'] / totale_utenti_mov) * 100
            })
        
        # Giacenze per stato
        cursor.execute("""
            SELECT stato, SUM(quantita) as quantita
            FROM giacenze
            WHERE quantita > 0
            GROUP BY stato
            ORDER BY quantita DESC
        """)
        stati_giacenze = cursor.fetchall()
        
        # Ultimi 20 movimenti
        cursor.execute("""
            SELECT 
                DATE_FORMAT(m.data_ora, '%%d/%%m/%%Y %%H:%%i') as data_ora,
                m.tipo_movimento as tipo,
                p.codice_prodotto as codice,
                p.nome_prodotto as prodotto,
                m.quantita,
                m.da_ubicazione,
                m.a_ubicazione,
                u.username as utente
            FROM movimenti m
            JOIN prodotti p ON m.prodotto_id = p.id
            JOIN utenti u ON m.user_id = u.id
            WHERE m.data_ora BETWEEN %s AND %s
            ORDER BY m.data_ora DESC
            LIMIT 20
        """, (start_date, end_date))
        ultimi_movimenti = cursor.fetchall()
        
        # Prodotti sotto soglia
        cursor.execute("""
            SELECT 
                p.codice_prodotto as codice,
                p.nome_prodotto as nome,
                COALESCE(SUM(g.quantita), 0) as giacenza,
                pt.soglia_minima as soglia,
                pt.soglia_minima - COALESCE(SUM(g.quantita), 0) as mancanti
            FROM product_thresholds pt
            JOIN prodotti p ON pt.codice_prodotto COLLATE utf8mb4_unicode_ci = p.codice_prodotto COLLATE utf8mb4_unicode_ci
            LEFT JOIN giacenze g ON p.id = g.prodotto_id
            WHERE pt.notifica_attiva = 1
            GROUP BY p.id, p.codice_prodotto, p.nome_prodotto, pt.soglia_minima
            HAVING giacenza < pt.soglia_minima
            ORDER BY mancanti DESC
            LIMIT 10
        """)
        prodotti_sotto_soglia = cursor.fetchall()
        
        # Movimenti per magazzino
        cursor.execute("""
            SELECT 
                COALESCE(mag.nome, 'Non specificato') as nome,
                SUM(CASE WHEN m.tipo_movimento = 'CARICO' THEN m.quantita ELSE 0 END) as entrate,
                SUM(CASE WHEN m.tipo_movimento = 'SCARICO' THEN m.quantita ELSE 0 END) as uscite
            FROM movimenti m
            LEFT JOIN magazzini mag ON m.a_magazzino_id = mag.id OR m.da_magazzino_id = mag.id
            WHERE m.data_ora BETWEEN %s AND %s
            GROUP BY COALESCE(mag.nome, 'Non specificato')
            ORDER BY (SUM(CASE WHEN m.tipo_movimento = 'CARICO' THEN m.quantita ELSE 0 END) + SUM(CASE WHEN m.tipo_movimento = 'SCARICO' THEN m.quantita ELSE 0 END)) DESC
            LIMIT 5
        """, (start_date, end_date))
        magazzini_raw = cursor.fetchall()
        
        # Calcola percentuali e saldo magazzini
        totale_mag_mov = sum(m['entrate'] + m['uscite'] for m in magazzini_raw) or 1
        magazzini = []
        for m in magazzini_raw:
            entrate = int(m['entrate'] or 0)
            uscite = int(m['uscite'] or 0)
            magazzini.append({
                'nome': m['nome'],
                'entrate': entrate,
                'uscite': uscite,
                'saldo': entrate - uscite,
                'percentuale': ((entrate + uscite) / totale_mag_mov) * 100
            })
        
        # === NUOVE QUERY PER STATISTICHE AVANZATE ===
        
        # Distribuzione per fascia oraria
        cursor.execute("""
            SELECT 
                HOUR(data_ora) as ora,
                COUNT(*) as num_movimenti,
                SUM(quantita) as quantita_totale
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY HOUR(data_ora)
            ORDER BY ora
        """, (start_date, end_date))
        fasce_orarie_raw = cursor.fetchall()
        
        # Crea array completo delle 24 ore
        fasce_orarie = []
        fasce_dict = {row['ora']: row for row in fasce_orarie_raw}
        for ora in range(24):
            if ora in fasce_dict:
                fasce_orarie.append({
                    'ora': f"{ora:02d}:00",
                    'movimenti': fasce_dict[ora]['num_movimenti'],
                    'quantita': int(fasce_dict[ora]['quantita_totale'] or 0)
                })
            else:
                fasce_orarie.append({'ora': f"{ora:02d}:00", 'movimenti': 0, 'quantita': 0})
        
        # Distribuzione per giorno della settimana
        cursor.execute("""
            SELECT 
                DAYOFWEEK(data_ora) as giorno_num,
                DAYNAME(data_ora) as giorno_nome,
                COUNT(*) as num_movimenti,
                SUM(quantita) as quantita_totale
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY DAYOFWEEK(data_ora), DAYNAME(data_ora)
            ORDER BY giorno_num
        """, (start_date, end_date))
        giorni_settimana_raw = cursor.fetchall()
        
        # Mappa nomi italiani
        giorni_it = {
            'Sunday': 'Domenica', 'Monday': 'Lunedì', 'Tuesday': 'Martedì',
            'Wednesday': 'Mercoledì', 'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato'
        }
        giorni_settimana = [{
            'giorno': giorni_it.get(row['giorno_nome'], row['giorno_nome']),
            'movimenti': row['num_movimenti'],
            'quantita': int(row['quantita_totale'] or 0)
        } for row in giorni_settimana_raw]
        
        # Metriche avanzate
        cursor.execute("""
            SELECT 
                COUNT(*) as totale_movimenti,
                COUNT(DISTINCT DATE(data_ora)) as giorni_attivi,
                COUNT(DISTINCT user_id) as utenti_attivi,
                MAX(quantita) as quantita_max_singola,
                MIN(quantita) as quantita_min_singola,
                AVG(quantita) as quantita_media,
                STDDEV(quantita) as quantita_stddev
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
        """, (start_date, end_date))
        metriche_db = cursor.fetchone()
        
        # Giorno con più movimenti
        cursor.execute("""
            SELECT 
                DATE(data_ora) as data,
                COUNT(*) as movimenti,
                SUM(quantita) as quantita
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY DATE(data_ora)
            ORDER BY movimenti DESC
            LIMIT 1
        """, (start_date, end_date))
        picco_giornaliero = cursor.fetchone()
        
        # Ora con più movimenti
        cursor.execute("""
            SELECT 
                HOUR(data_ora) as ora,
                COUNT(*) as movimenti
            FROM movimenti
            WHERE data_ora BETWEEN %s AND %s
            GROUP BY HOUR(data_ora)
            ORDER BY movimenti DESC
            LIMIT 1
        """, (start_date, end_date))
        ora_piu_attiva = cursor.fetchone()
        
        metriche_avanzate = {
            'giorni_totali_periodo': giorni_periodo,
            'giorni_attivi': metriche_db['giorni_attivi'] or 0,
            'giorni_inattivi': giorni_periodo - (metriche_db['giorni_attivi'] or 0),
            'utenti_attivi': metriche_db['utenti_attivi'] or 0,
            'media_movimenti_giorno': round((metriche_db['totale_movimenti'] or 0) / (metriche_db['giorni_attivi'] or 1), 1),
            'quantita_max_singola': int(metriche_db['quantita_max_singola'] or 0),
            'quantita_min_singola': int(metriche_db['quantita_min_singola'] or 0),
            'quantita_media': round(float(metriche_db['quantita_media'] or 0), 1),
            'quantita_deviazione_std': round(float(metriche_db['quantita_stddev'] or 0), 1),
            'picco_giornaliero': {
                'data': picco_giornaliero['data'].strftime('%d/%m/%Y') if picco_giornaliero and picco_giornaliero['data'] else '-',
                'movimenti': picco_giornaliero['movimenti'] if picco_giornaliero else 0,
                'quantita': int(picco_giornaliero['quantita'] or 0) if picco_giornaliero else 0
            },
            'ora_piu_attiva': f"{ora_piu_attiva['ora']:02d}:00" if ora_piu_attiva else '-'
        }
        
        cursor.close()
        conn.close()
        
        # Genera grafico trend
        trend_chart_base64 = ''
        if trend_data:
            fig, ax = plt.subplots(figsize=(10, 4))
            
            if range_param in ['6m', '1y']:
                labels = [row['periodo'] for row in trend_data]
            else:
                labels = [row['periodo'].strftime('%d/%m') if hasattr(row['periodo'], 'strftime') else str(row['periodo']) for row in trend_data]
            
            carichi = [int(row['carichi'] or 0) for row in trend_data]
            scarichi = [int(row['scarichi'] or 0) for row in trend_data]
            
            ax.plot(labels, carichi, label='Carichi', color='#22c55e', linewidth=2, marker='o', markersize=4)
            ax.plot(labels, scarichi, label='Scarichi', color='#ef4444', linewidth=2, marker='o', markersize=4)
            ax.fill_between(labels, carichi, alpha=0.1, color='#22c55e')
            ax.fill_between(labels, scarichi, alpha=0.1, color='#ef4444')
            ax.set_xlabel('Periodo')
            ax.set_ylabel('Quantità')
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            trend_chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # Genera grafico distribuzione per tipo (pie)
        pie_chart_base64 = ''
        if totale_carichi > 0 or totale_scarichi > 0 or totale_trasferimenti > 0:
            fig, ax = plt.subplots(figsize=(5, 5))
            labels = []
            sizes = []
            colors = []
            explode = []
            
            if totale_carichi > 0:
                labels.append(f'Carichi\n({totale_carichi})')
                sizes.append(totale_carichi)
                colors.append('#22c55e')
                explode.append(0.02)
            if totale_scarichi > 0:
                labels.append(f'Scarichi\n({totale_scarichi})')
                sizes.append(totale_scarichi)
                colors.append('#ef4444')
                explode.append(0.02)
            if totale_trasferimenti > 0:
                labels.append(f'Trasferimenti\n({totale_trasferimenti})')
                sizes.append(totale_trasferimenti)
                colors.append('#3b82f6')
                explode.append(0.02)
            
            wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, 
                                               autopct='%1.1f%%', startangle=90,
                                               explode=explode, shadow=True)
            for autotext in autotexts:
                autotext.set_fontsize(9)
                autotext.set_fontweight('bold')
            ax.axis('equal')
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            pie_chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # Genera grafico confronto periodi (bar chart)
        bar_chart_base64 = ''
        if kpi_prev['totale_movimenti'] and kpi_prev['totale_movimenti'] > 0:
            fig, ax = plt.subplots(figsize=(8, 4))
            
            categories = ['Movimenti', 'Carichi', 'Scarichi', 'Trasferimenti']
            current_values = [totale_movimenti, totale_carichi, totale_scarichi, totale_trasferimenti]
            prev_values = [
                kpi_prev['totale_movimenti'] or 0,
                int(kpi_prev['totale_carichi'] or 0),
                int(kpi_prev['totale_scarichi'] or 0),
                int(kpi_prev['totale_trasferimenti'] or 0)
            ]
            
            x = range(len(categories))
            width = 0.35
            
            bars1 = ax.bar([i - width/2 for i in x], prev_values, width, label='Periodo Precedente', color='#94a3b8')
            bars2 = ax.bar([i + width/2 for i in x], current_values, width, label='Periodo Corrente', color='#0056a6')
            
            ax.set_ylabel('Quantità')
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')
            
            # Aggiungi valori sopra le barre
            for bar in bars1:
                height = bar.get_height()
                ax.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            for bar in bars2:
                height = bar.get_height()
                ax.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
            
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            bar_chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # === NUOVI GRAFICI ===
        
        # Grafico distribuzione oraria
        oraria_chart_base64 = ''
        fasce_con_dati = [f for f in fasce_orarie if f['movimenti'] > 0]
        if fasce_con_dati:
            fig, ax = plt.subplots(figsize=(12, 4))
            
            ore = [f['ora'] for f in fasce_orarie]
            movimenti = [f['movimenti'] for f in fasce_orarie]
            max_val = max(movimenti) if movimenti else 1
            
            colors = ['#ef4444' if v == max_val else '#f59e0b' if v > max_val * 0.7 else '#0056a6' for v in movimenti]
            
            ax.bar(ore, movimenti, color=colors, edgecolor='white', linewidth=0.5)
            ax.set_xlabel('Ora del giorno')
            ax.set_ylabel('Numero Movimenti')
            ax.set_title('Distribuzione Oraria delle Operazioni')
            ax.grid(True, alpha=0.3, axis='y')
            plt.xticks(rotation=45, ha='right', fontsize=8)
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            oraria_chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # Grafico distribuzione settimanale
        settimanale_chart_base64 = ''
        if giorni_settimana:
            fig, ax1 = plt.subplots(figsize=(10, 4))
            
            giorni = [g['giorno'] for g in giorni_settimana]
            mov = [g['movimenti'] for g in giorni_settimana]
            qta = [g['quantita'] for g in giorni_settimana]
            
            x = range(len(giorni))
            bars = ax1.bar(x, mov, color='#0056a6', alpha=0.8, label='N° Movimenti')
            ax1.set_ylabel('Numero Movimenti', color='#0056a6')
            ax1.tick_params(axis='y', labelcolor='#0056a6')
            ax1.set_xticks(x)
            ax1.set_xticklabels(giorni)
            
            ax2 = ax1.twinx()
            ax2.plot(x, qta, color='#22c55e', marker='o', linewidth=2, label='Quantità Totale')
            ax2.fill_between(x, qta, alpha=0.1, color='#22c55e')
            ax2.set_ylabel('Quantità Totale', color='#22c55e')
            ax2.tick_params(axis='y', labelcolor='#22c55e')
            
            ax1.set_title('Attività per Giorno della Settimana')
            ax1.grid(True, alpha=0.3, axis='y')
            
            # Legenda combinata
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
            
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            settimanale_chart_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
        
        # Range label mapping
        range_labels = {
            '7d': 'Ultimi 7 giorni',
            '30d': 'Ultimi 30 giorni',
            '90d': 'Ultimi 90 giorni',
            '6m': 'Ultimi 6 mesi',
            '1y': 'Ultimo anno'
        }
        
        # Render HTML per PDF
        html_content = flask_render_template('statistiche_pdf.html',
            periodo_inizio=start_date.strftime('%d/%m/%Y'),
            periodo_fine=end_date.strftime('%d/%m/%Y'),
            periodo_precedente=f"{prev_start.strftime('%d/%m/%Y')} - {prev_end.strftime('%d/%m/%Y')}",
            range_label=range_labels.get(range_param, range_param),
            kpi=kpi,
            trend_chart=trend_chart_base64,
            pie_chart=pie_chart_base64,
            bar_chart=bar_chart_base64,
            oraria_chart=oraria_chart_base64,
            settimanale_chart=settimanale_chart_base64,
            top_prodotti=top_prodotti,
            utenti=utenti,
            stati_giacenze=stati_giacenze,
            ultimi_movimenti=ultimi_movimenti,
            prodotti_sotto_soglia=prodotti_sotto_soglia,
            magazzini=magazzini if magazzini else None,
            fasce_orarie=fasce_orarie,
            giorni_settimana=giorni_settimana,
            metriche_avanzate=metriche_avanzate,
            generated_at=datetime.now().strftime('%d/%m/%Y %H:%M'),
            anno_corrente=datetime.now().year
        )
        
        # Genera PDF
        pdf = HTML(string=html_content).write_pdf()
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=report_statistiche_{range_param}_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
        
        return response
        
    except ImportError as ie:
        return jsonify({'error': f'Dipendenza mancante: {str(ie)}. Installa weasyprint e matplotlib.'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
