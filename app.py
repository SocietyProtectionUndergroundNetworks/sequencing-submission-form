# app.py (This is your main entry point for running the Flask app)

import os

# Import the create_app factory from your main app package
# Adjust 'flask_app' to your actual package name if different
from flask_app import create_app

# Create the Flask application instance using the factory
# This will use the default (non-test) configuration
app = create_app()

if __name__ == "__main__":
    server_port = os.environ.get("PORT", "56733")
    app.run(debug=True, host="0.0.0.0", port=int(server_port))
