"""
Routes per il pannello amministratore.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database_connection import connect_to_database
from utils.decorators import admin_required, api_admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('')
@admin_required
def admin_panel():
    """Dashboard principale del pannello admin."""
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


@admin_bp.route('/users')
@admin_required
def admin_users():
    """Gestione utenti per admin."""
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


@admin_bp.route('/broadcast', methods=['POST'])
@api_admin_required
def admin_broadcast():
    """Invia una notifica broadcast a tutti gli utenti."""
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
