"""
Routes per autenticazione: login, logout, gestione utenti.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from database_connection import connect_to_database
from utils.decorators import admin_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Gestisce il login degli utenti."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, password_hash, is_admin FROM utenti WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = username
            session['is_admin'] = user.get('is_admin', False)
            flash('Login effettuato con successo', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username o password errati', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Effettua il logout dell'utente."""
    session.clear()
    flash('Logout effettuato', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    """
    Gestione utenti: aggiunta, eliminazione, modifica privilegi.
    Solo admin può accedere.
    """
    utenti = []
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, is_admin FROM utenti ORDER BY username ASC")
        utenti = cursor.fetchall()
        cursor.close()
        conn.close()
    except Exception as e:
        utenti = []
        flash(f"Errore nel recupero utenti: {e}", "error")

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_user':
            return _handle_add_user()
        elif action == 'delete_user':
            return _handle_delete_user()
        elif action == 'toggle_admin':
            return _handle_toggle_admin()

    return render_template('register.html', utenti=utenti, current_user_id=session.get('user_id'))


def _handle_add_user():
    """Gestisce l'aggiunta di un nuovo utente."""
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    is_admin = 1 if request.form.get('is_admin') == 'on' else 0

    if not username or not password or not confirm_password:
        flash('Tutti i campi sono obbligatori.', 'error')
        return redirect(url_for('auth.register'))

    if password != confirm_password:
        flash('Le password non coincidono.', 'error')
        return redirect(url_for('auth.register'))

    password_hash = generate_password_hash(password)

    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO utenti (username, password_hash, is_admin) VALUES (%s, %s, %s)", 
            (username, password_hash, is_admin)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash(f'Utente {username} aggiunto con successo.', 'success')
    except mysql.connector.IntegrityError:
        flash('Username già esistente. Scegli un altro username.', 'error')
    except Exception as e:
        flash(f'Errore durante la registrazione: {e}', 'error')
    
    return redirect(url_for('auth.register'))


def _handle_delete_user():
    """Gestisce l'eliminazione di un utente."""
    user_id = request.form.get('user_id')
    
    # Non permettere l'eliminazione dell'utente corrente
    if int(user_id) == session.get('user_id'):
        flash('Non puoi eliminare il tuo account mentre sei loggato.', 'error')
        return redirect(url_for('auth.register'))
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM utenti WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute("DELETE FROM utenti WHERE id = %s", (user_id,))
            conn.commit()
            flash(f'Utente {user["username"]} eliminato con successo.', 'success')
        
        cursor.close()
        conn.close()
    except Exception as e:
        flash(f'Errore durante l\'eliminazione: {e}', 'error')
    
    return redirect(url_for('auth.register'))


def _handle_toggle_admin():
    """Gestisce la modifica dei privilegi admin."""
    user_id = request.form.get('user_id')
    new_status = request.form.get('new_status')
    
    try:
        conn = connect_to_database()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM utenti WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute("UPDATE utenti SET is_admin = %s WHERE id = %s", (new_status, user_id))
            conn.commit()
            status_text = "amministratore" if int(new_status) == 1 else "utente normale"
            flash(f'{user["username"]} è ora {status_text}.', 'success')
        
        cursor.close()
        conn.close()
    except Exception as e:
        flash(f'Errore durante l\'aggiornamento: {e}', 'error')
    
    return redirect(url_for('auth.register'))
