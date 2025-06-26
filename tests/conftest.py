import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import your Base and Flask app factory
from models.db_model import Base
from flask_app import (
    create_app,
)
import helpers.dbm as original_dbm_module


@pytest.fixture(scope="session")
def app():
    """Creates and configures a Flask app with a real MySQL test database."""
    test_config = {
        "TESTING": True,
        "DISABLE_EARTH_ENGINE": True,
        "SQLALCHEMY_DATABASE_URI": (
            "mysql+mysqldb://flask:flask@mysql_test:3306/flask_test"
            "?charset=utf8mb4"
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "CELERY_ALWAYS_EAGER": True,
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "memory://",
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "SESSION_TYPE": "filesystem",
    }

    app = create_app(test_config)

    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app, mocker):
    """
    Provides a clean DB session using the real MySQL test DB,
    and patches dbm.connect_db().
    """
    # Get the real engine from the configured URI
    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    # Patch connect_db() so any call to session_scope() uses this MySQL engine
    mocker.patch.object(original_dbm_module, "connect_db", return_value=engine)

    with app.app_context():
        # Setup schema before test
        Base.metadata.create_all(bind=engine)
        session = TestingSessionLocal()
        yield session
        session.close()
        # Teardown schema after test
        Base.metadata.drop_all(bind=engine)
