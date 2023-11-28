import os
import sys
import secrets
import math
import json
import sqlite3
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from oauthlib.oauth2 import WebApplicationClient
import requests
from werkzeug.utils import secure_filename

# Library about google cloud storage
from google.cloud import storage

# Internal imports
from db import init_db_command
from user import User

app = Flask(__name__)
foo = secrets.token_urlsafe(16)
app.secret_key = foo

# Configure login via google
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
GOOGLE_DISCOVERY_URL = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# Configure Google Cloud Storage
bucket_name = os.environ.get('GOOGLE_STORAGE_BUCKET_NAME')
project_id = os.environ.get('GOOGLE_STORAGE_PROJECT_ID')
bucket_location = os.environ.get('GOOGLE_STORAGE_BUCKET_LOCATION')

# User session management setup
# https://flask-login.readthedocs.io/en/latest
login_manager = LoginManager()
login_manager.init_app(app)

# Naive database setup
try:
    init_db_command()
except sqlite3.OperationalError:
    # Assume it's already been created
    pass

# OAuth 2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)

# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()

def get_progress(file_uuid):
    try:
        with open("upload_progress.json", "r") as file:
            progress_data = json.load(file)
            return progress_data.get(file_uuid, 0)
    except FileNotFoundError:
        return 0

def update_progress(file_uuid, percentage):
    try:
        with open("upload_progress.json", "r") as file:
            progress_data = json.load(file)
    except FileNotFoundError:
        progress_data = {}

    progress_data[file_uuid] = percentage

    with open("upload_progress.json", "w") as file:
        json.dump(progress_data, file)

def chunked_upload(local_file_path, destination_blob_name, file_uuid, bucket_name):
    chunk_size = 20 * 1024 * 1024  # 20 MB chunk size

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(f'uploads/{destination_blob_name}')

    temp_directory = f"temp_{file_uuid}"

    total_size = os.path.getsize(local_file_path)
    uploaded_bytes = 0

    with open(local_file_path, 'rb') as file:
        blob.chunk_size = chunk_size
        chunk_num = 0
        chunks = []

        while True:
            data = file.read(chunk_size)
            if not data:
                break

            temp_blob = bucket.blob(f'uploads/{temp_directory}/{destination_blob_name}.part{chunk_num}')
            temp_blob.upload_from_string(data, content_type='application/octet-stream')
            chunks.append(temp_blob)
            chunk_num += 1

            uploaded_bytes += len(data)
            percentage = (uploaded_bytes / total_size) * 100
            update_progress(file_uuid, percentage)
            print(f"Bytes uploaded: {uploaded_bytes} / {total_size} ({percentage:.2f}%)", flush=True)

        blob.compose(chunks)

        for temp_blob in chunks:
            temp_blob.delete()

        update_progress(file_uuid, 100)
        print(f"File {local_file_path} uploaded to {destination_blob_name} in {bucket_name} bucket.", flush=True)

        

@app.route("/")
def index():
    if current_user.is_authenticated:
        return (
            "<p>Hello, {}! You're logged in! Email: {}</p>"
            "<div><p>Google Profile Picture:</p>"
            '<img src="{}" alt="Google profile pic"></img></div>'
            '<a class="button" href="/logout">Logout</a>'.format(
                current_user.name, current_user.email, current_user.profile_pic
            )
        )
    else:
        return '<a class="button" href="/login">Google Login</a>'

@app.route("/login")
def login():
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for login and provide
    # scopes that let you retrieve user's profile from Google
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "/callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@app.route("/login/callback")
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
        redirect_url=request.base_url,
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
        id_=unique_id, name=users_name, email=users_email, profile_pic=picture
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):
        User.create(unique_id, users_name, users_email, picture)

    # Begin user session by logging the user in
    login_user(user)

    # Send user back to homepage
    return redirect(url_for("index"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.get("/form")
@login_required
def upload_form():
    return render_template("index.html")

@app.post("/upload")
@login_required
def upload_chunked():
    file = request.files["file"]
    file_uuid = request.form["dzuuid"]
    # Generate a unique filename to avoid overwriting using 8 chars of uuid before filename.
    filename = f"{file_uuid[:8]}_{secure_filename(file.filename)}"
    save_path = Path("uploads", filename)
    current_chunk = int(request.form["dzchunkindex"])

    try:
        with open(save_path, "ab") as f:
            f.seek(int(request.form["dzchunkbyteoffset"]))
            f.write(file.stream.read())
    except OSError:
        return "Error saving file.", 500

    total_chunks = int(request.form["dztotalchunkcount"])

    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form["dztotalfilesize"]):
            return "Size mismatch.", 500
        else:
            chunked_upload(save_path, filename, file_uuid, bucket_name)

    return "Chunk upload successful.", 200

@app.get("/uploadprogress")
def api_progress():
    file_uuid = request.args.get('file_uuid')
    progress = get_progress(file_uuid)
    return {
        "progress": progress
    }    
    

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    #serve(app, host="0.0.0.0", port=server_port)
    app.run(debug=True, port=server_port, host='0.0.0.0')
