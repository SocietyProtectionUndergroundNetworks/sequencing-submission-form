import os
import secrets

from flask import Flask
from views import user, upload
from extensions import login_manager

app = Flask(__name__)
foo = secrets.token_urlsafe(16)
app.secret_key = foo

# Register blueprints (assuming you're using blueprints in your views)
app.register_blueprint(user.user_bp)
app.register_blueprint(upload.upload_bp)

# Initialize extensions
login_manager.init_app(app)

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    #serve(app, host="0.0.0.0", port=server_port)
    app.run(debug=True, port=server_port, host='0.0.0.0')