import os
from flask import Flask
from apps import create_app
from apps.config import Config

# Create Flask app using factory pattern
# The create_app function registers the 'format_currency' filter automatically.
app = create_app(Config)

def run_flask():
    """Run Flask app."""
    # Removed: app.jinja_env.filters['format_currency'] = format_currency
    # The filter is already registered inside create_app() in apps/__init__.py
    app.run(debug=app.config['DEBUG'], use_reloader=False)


if __name__ == "__main__":
    run_flask()
