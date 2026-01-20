"""
Decoratori per autenticazione e autorizzazione.
Centralizza i controlli ripetuti in tutto il codebase.
"""
from functools import wraps
from flask import session, redirect, url_for, flash, jsonify


def login_required(f):
    """
    Decoratore per proteggere le route che richiedono autenticazione.
    Redirect a login se non autenticato.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Devi effettuare il login per accedere a questa pagina.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decoratore per proteggere le route che richiedono privilegi admin.
    Redirect a index se non admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Devi effettuare il login per accedere a questa pagina.', 'warning')
            return redirect(url_for('auth.login'))
        if not session.get('is_admin', False):
            flash('Accesso negato. Solo gli amministratori possono accedere a questa sezione.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """
    Decoratore per proteggere le API che richiedono autenticazione.
    Restituisce JSON error 401 se non autenticato.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Non autorizzato'}), 401
        return f(*args, **kwargs)
    return decorated_function


def api_admin_required(f):
    """
    Decoratore per proteggere le API che richiedono privilegi admin.
    Restituisce JSON error 403 se non admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Non autorizzato'}), 401
        if not session.get('is_admin', False):
            return jsonify({'error': 'Accesso negato. Richiesti privilegi admin.'}), 403
        return f(*args, **kwargs)
    return decorated_function
