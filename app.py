import os
from flask import Flask
from apps import create_app
from apps.config import Config
import uvicorn
import multiprocessing
from apps.fastapi_app import fastapi_app  # Import FastAPI instance

# Create Flask app using factory pattern
app = create_app(Config)

def run_flask():
    """Run Flask app."""
    app.run(debug=app.config['DEBUG'], use_reloader=False)  # Prevent Flask from running twice

def run_fastapi():
    """Run FastAPI app."""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8001)

if __name__ == "__main__":
    # Run Flask and FastAPI in separate processes
    flask_process = multiprocessing.Process(target=run_flask)
    fastapi_process = multiprocessing.Process(target=run_fastapi)

    flask_process.start()
    fastapi_process.start()

    flask_process.join()
    fastapi_process.join()
