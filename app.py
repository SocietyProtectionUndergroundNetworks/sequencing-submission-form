import os
import secrets
import logging

from views import create_app
from extensions import login_manager
from celery_config import make_celery
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from db.db_conn import get_database_uri

app = create_app()
SQLALCHEMY_DATABASE_URI = get_database_uri()

app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
db = SQLAlchemy(app)

app.config["SESSION_TYPE"] = "sqlalchemy"
app.config["SESSION_SQLALCHEMY"] = db
Session(app)

# Secret key generation
foo = secrets.token_urlsafe(16)
app.secret_key = foo

# Initialize extensions
login_manager.init_app(app)


logger = logging.getLogger(
    "my_app_logger"
)  # Use the same name when retrieving the logger

# Initialize Celery
# logger.info("Initializing Celery...")
celery = make_celery(app)
# logger.info("Celery initialized successfully!")

# Import tasks after Celery is initialized
import tasks  # noqa: E402, F401

if __name__ == "__main__":
    server_port = os.environ.get("PORT", "8080")
    app.run(debug=True, port=server_port, host="0.0.0.0")
