# views/__init__.py

import logging
from flask import Flask

# Import your blueprints
from .admin import admin_bp
from .user import user_bp
from .upload import upload_bp
from .data import data_bp
from .ecoregions import ecoregions_bp
from .scripps import scripps_bp
from .buckets import bucket_bp
from .taxonomy import taxonomy_bp
from .projects import projects_bp
from .sequencing_upload_form import upload_form_bp
from .documentation import documentation_bp


def create_base_app():  # Renamed from create_app
    """
    Creates a basic Flask app instance and registers blueprints.
    This function does NOT handle database, sessions, or other extensions.
    """
    app = Flask(
        __name__, static_folder="../static", template_folder="../templates"
    )

    # Configure logging
    # (this will still happen, but the main app
    # factory can override/augment it)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s 1 [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log"),  # Log to a file
            logging.StreamHandler(),  # Log to console
        ],
    )
    logger = logging.getLogger("my_app_logger")  # noqa: F841

    # Register Blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(scripps_bp)
    app.register_blueprint(bucket_bp)
    app.register_blueprint(taxonomy_bp)
    app.register_blueprint(ecoregions_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(upload_form_bp)
    app.register_blueprint(documentation_bp)

    return app
