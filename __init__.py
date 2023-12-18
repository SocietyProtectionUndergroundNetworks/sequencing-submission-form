from flask import Flask
from .views.auth import auth_bp
from .views.upload import upload_bp
from .models.user import User
from .models.upload import Upload

def create_app():
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)

    return app