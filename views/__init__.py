import logging
from flask import Flask
from .user import user_bp
from .upload import upload_bp
from .data import data_bp
from .metadata import metadata_bp
from .scripps import scripps_bp
from .buckets import bucket_bp
from .taxonomy import taxonomy_bp


def create_app():
    app = Flask(
        __name__, static_folder="../static", template_folder="../templates"
    )

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,  # Set the logging level as per your need
        format="%(asctime)s 1 [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log"),  # Log to a file
            logging.StreamHandler(),  # Log to console
        ],
    )
    logger = logging.getLogger("my_app_logger")  # noqa: F841
    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(metadata_bp)
    app.register_blueprint(scripps_bp)
    app.register_blueprint(bucket_bp)
    app.register_blueprint(taxonomy_bp)

    return app
