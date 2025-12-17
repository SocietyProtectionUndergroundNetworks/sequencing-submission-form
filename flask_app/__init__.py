# flask_app/__init__.py

import secrets
import sys
import logging
import os

# Import extensions without initializing them with an app yet
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

# Import your helpers and modules
from db.db_conn import (
    get_database_uri,
)
from views import create_base_app
from extensions import login_manager
from celery_config import make_celery
from celery.schedules import crontab

# Initialize extensions as objects, to be bound to an app later
db = SQLAlchemy()
sess = Session()
celery_app = (
    None  # Placeholder for your Celery instance, global for worker entry
)


def create_app(test_config=None):
    global celery_app
    app = create_base_app()

    # Clear current_app.logger handlers if any
    if app.logger.hasHandlers():
        app.logger.handlers.clear()

    # Also clear root logger handlers to avoid duplicates
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set levels
    app.logger.setLevel(logging.DEBUG)
    root_logger.setLevel(logging.DEBUG)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    # Use the first one if you want to show the name of the logging handler.
    # formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)

    # Attach handler only once
    app.logger.addHandler(handler)
    root_logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs on current_app.logger
    app.logger.propagate = False

    # 2. Apply configuration based on environment or test_config
    # Default configuration (for development/production)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False  # Good practice

    if test_config is None:
        # Load default database and session config
        app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
        app.config["SESSION_TYPE"] = "sqlalchemy"
        app.config["SESSION_SQLALCHEMY"] = db

        # Celery configuration for non-testing environments
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
            CELERY_ALWAYS_EAGER=False,
        )
        # Secret key generation
        app.secret_key = secrets.token_urlsafe(
            16
        )  # Generate a new one each time

    else:
        # Load the test configuration if passed in (e.g., from pytest)
        app.config.from_mapping(test_config)
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
    # Conditionally initialize Earth Engine only if NOT disabled
    # Disabled if "ENVIRONMENT" is set to development in .env
    env = os.getenv("ENVIRONMENT", "development")
    app.config["DISABLE_EARTH_ENGINE"] = env != "production"
    if not app.config["DISABLE_EARTH_ENGINE"]:
        from helpers.land_use import initialize_earth_engine
        initialize_earth_engine()

    # Logger setup (your views/__init__.py might also do this,
    # but this is the main app logger)
    logging.getLogger("my_app_logger")

    # 5. Initialize the global Celery app instance
    # This must be done AFTER app.config is fully set up
    celery_app = make_celery(app)

    celery_app.conf.beat_schedule = {
        "send_vm_status_every_morning_7am": {
            "task": "tasks.send_vm_status_to_slack_task",
            "schedule": crontab(hour=7, minute=0),  # every day at 07:00
        },
    }

    # 6. Import tasks AFTER Celery is initialized
    # This is crucial for Celery to register tasks correctly.
    # Adjust 'tasks' if it's within a package, e.g., 'flask_app.tasks'
    import tasks  # noqa: E402, F401

    return app


# The global 'app' variable (if uncommented) for WSGI servers
# app = create_app()
