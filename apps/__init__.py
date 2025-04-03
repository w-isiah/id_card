import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from importlib import import_module
from apps.config import Config  # Import configuration
from apps.db import get_db_connection  # Import DB connection function

# Initialize extensions
csrf = CSRFProtect()

def register_extensions(app):
    """Register Flask extensions."""
    csrf.init_app(app)

def register_blueprints(app):
    """Dynamically register blueprints from the apps module."""
    modules = ['authentication', 'home', 'products', 'customers', 'categories','p_restock']
    for module_name in modules:
        module = import_module(f'apps.{module_name}.routes')
        app.register_blueprint(module.blueprint)

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register extensions and blueprints
    register_extensions(app)
    register_blueprints(app)

    return app
