# flask_app/__init__.py

import os
import secrets
import logging
from flask import Flask

# Import extensions without initializing them with an app yet
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

# Import your helpers and modules
from db.db_conn import (
    get_database_uri,
)  # Your function to get the default MySQL URI
from models.db_model import Base  # Your SQLAlchemy declarative_base
from views import create_base_app  # Import the function from views/__init__.py
from extensions import login_manager  # Your Flask-Login manager
from celery_config import make_celery  # Your Celery factory/instance

# Initialize extensions as objects, to be bound to an app later
db = SQLAlchemy()
sess = Session()
celery_app = (
    None  # Placeholder for your Celery instance, global for worker entry
)


def create_app(test_config=None):
    """
    Main Flask application factory.
    Args:
        test_config (dict): Optional configuration for testing.
                            If provided, it overrides default config.
    Returns:
        Flask.app: The fully configured Flask application instance.
    """
    # 1. Create the basic Flask app and register blueprints using your existing function
    app = create_base_app()  # Calls the create_app() from views/__init__.py

    # 2. Apply configuration based on environment or test_config
    # Default configuration (for development/production)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Good practice

    if test_config is None:
        # Load default database and session config
        app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
        app.config["SESSION_TYPE"] = "sqlalchemy"
        app.config["SESSION_SQLALCHEMY"] = (
            db  # This will be bound after db.init_app(app)
        )

        # Celery configuration for non-testing environments (matches your original app.py)
        app.config.update(
            CELERY_BROKER_URL="redis://redis:6379/0",
            CELERY_RESULT_BACKEND="redis://redis:6379/0",
            CELERY_ACCEPT_CONTENT=["json"],
            CELERY_RESULT_SERIALIZER="json",
            CELERY_TASK_SERIALIZER="json",
            CELERY_TASK_ACKS_LATE=True,
            CELERY_WORKER_PREFETCH_MULTIPLIER=1,
            CELERY_TASK_TIME_LIMIT=86400,  # 24 hours
            CELERY_BROKER_TRANSPORT_OPTIONS={"visibility_timeout": 86400},
            CELERY_ALWAYS_EAGER=False,  # Default for production/dev
        )
        # Secret key generation
        app.secret_key = secrets.token_urlsafe(
            16
        )  # Generate a new one each time

    else:
        # Load the test configuration if passed in (e.g., from pytest)
        app.config.from_mapping(test_config)
        # For testing, ensure Celery is eager unless specifically testing async behavior
        app.config["CELERY_ALWAYS_EAGER"] = app.config.get(
            "CELERY_ALWAYS_EAGER", True
        )
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config.get(
            "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"
        )
        app.config["SESSION_TYPE"] = app.config.get(
            "SESSION_TYPE", "filesystem"
        )
        app.config["SESSION_SQLALCHEMY"] = db
        app.secret_key = app.config.get(
            "SECRET_KEY", "test-secret-key-for-testing-only"
        )  # Use test key

    # 3. Initialize Flask extensions with the app instance
    db.init_app(app)  # Initialize SQLAlchemy with the configured app
    sess.init_app(app)  # Initialize Flask-Session
    login_manager.init_app(app)  # Initialize Flask-Login

    # 4. Other app setup that needs the app context or configuration
    # Initialize Earth Engine. This often needs to be mocked in tests.
    from helpers.land_use import initialize_earth_engine  # Assuming it's here

    initialize_earth_engine()  # For unit tests, you'll need to mock this out.

    # Logger setup (your views/__init__.py might also do this, but this is the main app logger)
    logging.getLogger("my_app_logger")

    # 5. Initialize the global Celery app instance
    # This must be done AFTER app.config is fully set up
    global celery_app
    celery_app = make_celery(app)

    # 6. Import tasks AFTER Celery is initialized
    # This is crucial for Celery to register tasks correctly.
    # Adjust 'tasks' if it's within a package, e.g., 'flask_app.tasks'
    import tasks  # noqa: E402, F401

    return app


# The global 'app' variable (if uncommented) for WSGI servers
# app = create_app()
