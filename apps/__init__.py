import os
from flask import Flask, session, g
from flask_wtf.csrf import CSRFProtect
from importlib import import_module
from apps.config import Config
from apps.db import get_db_connection
from datetime import timedelta  # Import timedelta here for session management


# Initialize extensions
csrf = CSRFProtect()

def register_extensions(app):
    """Register Flask extensions."""
    csrf.init_app(app)

def register_blueprints(app):
    """Dynamically register blueprints from the apps module."""
    modules = ['authentication', 'home', 'pupils', 'classes', 'fathers', 'mothers', 'guardians', 'subjects', 'teachers', 'gen_ids', 'study_years', 'results', 'reports','grades','dorms','register','promote','streams','rooms','stream_assign', 'categories', 'products','p_restock','dorm_reg', 'sub_categories','sales','customers','other_products','department_h_products','dep_restock','division','subject_assign']
    for module_name in modules:
        module = import_module(f'apps.{module_name}.routes')
        app.register_blueprint(module.blueprint)

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # Register extensions and blueprints
    register_extensions(app)
    register_blueprints(app)

    # Add a before_request function to retrieve user ID
    @app.before_request
    def before_request():
        """Set up user session data before each request."""
        # Fetch user_id from the session and store it in g for easy access throughout the app
        g.user_id = session.get('id')  # Use g to store global request-specific data

    return app
