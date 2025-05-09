# apps/config.py
import random
import string
import os
from datetime import timedelta

class Config:
    """Base configuration class."""
    basedir = os.path.abspath(os.path.dirname(__file__))

    # Upload folder paths
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls'}

    # Secret key for Flask
    SECRET_KEY = ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    # MySQL Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'id_card')

    # Session timeout (7 days)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    @staticmethod
    def init_app(app):
        """Initialize the app with the configuration."""
        app.config.from_object(Config)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)