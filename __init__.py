from flask import Flask
from .views.auth import auth_bp
from .views.upload import upload_bp
from .models.user import User
from .models.upload import Upload
