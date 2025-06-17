# celery_worker.py

from flask_app import create_app, celery_app

# Initialize the Flask app first
flask_app = create_app()

# The Celery app is available via the global `celery_app`
app = celery_app
