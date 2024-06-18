from flask import Flask
from .user import user_bp
from .upload import upload_bp
from .data import data_bp
from .metadata import metadata_bp


def create_app():
    app = Flask(
        __name__, static_folder="../static", template_folder="../templates"
    )

    # Register Blueprints
    app.register_blueprint(user_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(metadata_bp)

    return app
