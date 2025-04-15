from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash("You must be logged in to view this page.", "warning")
            return redirect(url_for('authentication_blueprint.login'))
        return f(*args, **kwargs)
    return decorated_function
