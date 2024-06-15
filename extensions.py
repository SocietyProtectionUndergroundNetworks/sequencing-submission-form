from flask_login import LoginManager

login_manager = LoginManager()
login_manager.session_protection = "strong"
# You can configure login_manager further if needed
