# tests/conftest.py (This remains as previously discussed)
import pytest
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# IMPORTANT: Import the actual module containing connect_db
import helpers.dbm as original_dbm_module

# Import your Base from where it's defined
from models.db_model import Base

# Import the main create_app factory and the shared db instance from your main app package
from flask_app import (
    create_app,
    db as flask_db_instance,
    celery_app as flask_celery_app,
)


@pytest.fixture(scope="session")
def app():
    """
    Creates and configures a new Flask app instance for the entire test session.
    It uses an in-memory SQLite database and eager Celery execution.
    """
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # In-memory SQLite for tests
        "CELERY_ALWAYS_EAGER": True,  # Ensures Celery tasks run synchronously in tests
        "CELERY_BROKER_URL": "memory://",  # In-memory broker for tests
        "CELERY_RESULT_BACKEND": "memory://",  # In-memory backend for tests
        "CELERY_ACCEPT_CONTENT": [
            "json"
        ],  # Ensure these are set for consistency
        "CELERY_RESULT_SERIALIZER": "json",
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_TASK_ACKS_LATE": False,  # Often set to False for eager testing to avoid unexpected re-executions
        "CELERY_WORKER_PREFETCH_MULTIPLIER": 0,  # Or 1, depending on how eager tests behave
        "CELERY_TASK_TIME_LIMIT": 1,  # Short limit for eager tests to fail fast if they hang
        "CELERY_BROKER_TRANSPORT_OPTIONS": {"visibility_timeout": 1},
        "SESSION_TYPE": "filesystem",  # Simpler session management for tests
        "SECRET_KEY": "test-secret-key-for-testing-only",  # Provide a secret key for testing
    }
    app = create_app(test_config)

    # Push an application context, which is often needed for db operations
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """A test client for the Flask app."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app, mocker):  # Keep 'mocker' in fixture arguments
    """
    Provides a SQLAlchemy session bound to the in-memory SQLite database
    for each test function. It handles schema creation and teardown.
    Crucially, it now mocks helpers.dbm.connect_db to return the in-memory engine.
    """
    # Get the in-memory SQLite engine that Flask-SQLAlchemy has already initialized
    # through the app fixture's configuration.
    test_engine = flask_db_instance.engine

    # 1. Mock helpers.dbm.connect_db to return our in-memory test engine.
    # This ensures that any call to connect_db() in your app (including via session_scope)
    # gets the test engine.
    mocker.patch.object(
        original_dbm_module, "connect_db", return_value=test_engine
    )

    # Now, if session_scope and get_session correctly call connect_db internally,
    # they will automatically use the mocked in-memory engine.
    # You no longer need these direct patches:
    # mocker.patch.object(original_dbm_module, 'session_scope', side_effect=mock_session_scope)
    # mocker.patch.object(original_dbm_module, 'get_session', side_effect=TestingSessionLocal)

    # Define the session class for direct use in the test if needed
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    # 2. Set up the in-memory database schema for the test
    with app.app_context():
        Base.metadata.create_all(bind=test_engine)
        # Yield a session for the test itself, allowing direct interaction
        # with the test database if needed within the test function.
        yield TestingSessionLocal()
        # 3. Teardown the schema after the test
        Base.metadata.drop_all(bind=test_engine)
