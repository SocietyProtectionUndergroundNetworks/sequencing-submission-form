import os
import requests
import json
import logging
from flask import request, redirect, url_for, render_template, session, Blueprint, jsonify
from oauthlib.oauth2 import WebApplicationClient
from extensions import login_manager
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from models.user import User
from helpers.bucket import list_buckets, get_project_resource_role_users, get_bucket_role_users

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

# Configure login via google
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_CLIENT_CALLBACK_URL = os.environ.get("GOOGLE_CLIENT_CALLBACK_URL", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)


# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

user_bp = Blueprint('user', __name__)

# Custom admin_required decorator
def admin_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(url_for('user.login'))  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for('user.only_admins'))
        return view_func(*args, **kwargs)
    return decorated_view

# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

@user_bp.route('/login')
def login():
    session['referrer_url'] = request.referrer

    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=GOOGLE_CLIENT_CALLBACK_URL,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@user_bp.route('/login/callback')
def callback():
    # Get authorization code Google sent back to you
    code = request.args.get("code")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send request to get tokens! Yay tokens!
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=GOOGLE_CLIENT_CALLBACK_URL,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens!
    client.parse_request_body_response(json.dumps(token_response.json()))

    # Now that we have tokens (yay) let's find and hit URL
    # from Google that gives you user's profile information,
    # including their Google Profile Image and Email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    # We want to make sure their email is verified.
    # The user authenticated with Google, authorized our
    # app, and now we've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        unique_id = userinfo_response.json()["sub"]
        users_email = userinfo_response.json()["email"]
        picture = userinfo_response.json()["picture"]
        users_name = userinfo_response.json()["given_name"]
    else:
        return "User email not available or not verified by Google.", 400

    # Create a user in our db with the information provided
    # by Google
    user = User(
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture, admin=False, approved=False
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):
        User.create(id_=unique_id, name=users_name, email=users_email, profile_pic=picture, admin=False, approved=False)

    # Begin user session by logging the user in
    login_user(user, remember=True)

    # After successful login, check if there's a referrer URL stored in the session
    if 'referrer_url' in session:
        referrer_url = session.pop('referrer_url')
        return redirect(referrer_url)
    else:
        # If there's no referrer URL stored, redirect to a default route
        return redirect(url_for("upload.index"))

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("upload.index"))

@login_manager.unauthorized_handler
def custom_unauthorized():
    # Customize the unauthorized page
    return render_template('public_homepage.html')

@user_bp.route('/only_admins')
def only_admins():
    return render_template('only_admins.html')

@user_bp.route('/only_approved')
def only_approved():
    return render_template('only_approved.html')

@user_bp.route('/users', endpoint='users')
@login_required
@admin_required
def users():
    all_users = User.get_all()
    all_buckets = list_buckets()
    return render_template('users.html', all_users=all_users, all_buckets=all_buckets)

@user_bp.route('/update_admin_status', methods=['POST'], endpoint='update_admin_status')
@login_required
@admin_required
def update_admin_status():
    user_id = request.form.get('user_id')
    admin_status = request.form.get('admin') == 'on'  # Convert to boolean
    # Update the admin status in the database based on user_id and admin_status
    User.update_admin_status(user_id, admin_status)
    return redirect('/users')

@user_bp.route('/update_approved_status', methods=['POST'], endpoint='update_approved_status')
@login_required
@admin_required
def update_approved_status():
    user_id = request.form.get('user_id')
    approved_status = request.form.get('approved') == 'on'  # Convert to boolean
    # Update the admin status in the database based on user_id and admin_status
    User.update_approved_status(user_id, approved_status)
    return redirect('/users')


@user_bp.route('/give_access_to_bucket', methods=['POST'], endpoint='give_access_to_bucket')
@login_required
@admin_required
def give_access_to_bucket():
    user_id = request.form.get('user_id')
    bucket = request.form.get('bucket')
    User.add_user_bucket_access(user_id, bucket)

    return redirect('/users')

@user_bp.route('/remove_access_from_bucket', methods=['POST'], endpoint='remove_access_from_bucket')
@login_required
@admin_required
def remove_access_from_bucket():
    user_id = request.form.get('user_id')
    bucket = request.form.get('bucket')

    User.delete_user_bucket_access(user_id, bucket)
    if User.has_bucket_access(user_id, bucket):
        return {'status': 0}
    else:
        return {'status': 1}
