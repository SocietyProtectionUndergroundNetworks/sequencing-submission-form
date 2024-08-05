import os
import requests
import json
import logging
from flask import (
    request,
    redirect,
    url_for,
    render_template,
    session,
    Blueprint,
)
from oauthlib.oauth2 import WebApplicationClient
from extensions import login_manager
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from models.user import User
from models.user_groups import UserGroups
from models.bucket import Bucket
from models.preapproved_user import PreapprovedUser
from helpers.bucket import list_buckets

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

user_bp = Blueprint("user", __name__)


# Custom admin_required decorator
def admin_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for("user.only_admins"))
        return view_func(*args, **kwargs)

    return decorated_view


# Flask-Login helper to retrieve a user from our db
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()


@user_bp.route("/login")
def login():
    session["referrer_url"] = request.referrer

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


@user_bp.route("/login/callback")
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
        id_=unique_id,
        name=users_name,
        email=users_email,
        profile_pic=picture,
        admin=False,
        approved=False,
    )

    # Doesn't exist? Add to database
    if not User.get(unique_id):

        preapproved_user = PreapprovedUser.get_by_email(users_email)
        if preapproved_user:
            user_id = User.create(
                id_=unique_id,
                name=users_name,
                email=users_email,
                profile_pic=picture,
                admin=False,
                approved=True,
            )
            logger.info("Created a preapproved user with user id")
            logger.info(user_id)
            # Additional logic to handle bucket and group assignment
            if preapproved_user.bucket:
                User.add_user_bucket_access(user_id, preapproved_user.bucket)
            if preapproved_user.group_id:
                User.add_user_group_access(user_id, preapproved_user.group_id)
            PreapprovedUser.delete(preapproved_user.id)
        else:
            User.create(
                id_=unique_id,
                name=users_name,
                email=users_email,
                profile_pic=picture,
                admin=False,
                approved=False,
            )

    # Begin user session by logging the user in
    login_user(user, remember=True)

    # After successful login,
    # check if there's a referrer URL stored in the session
    if "referrer_url" in session:
        referrer_url = session.pop("referrer_url")
        return redirect(referrer_url)
    else:
        # If there's no referrer URL stored, redirect to a default route
        return redirect(url_for("upload.index"))


@user_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("upload.index"))


@login_manager.unauthorized_handler
def custom_unauthorized():
    # Customize the unauthorized page
    return render_template("public_homepage.html")


@user_bp.route("/only_admins")
def only_admins():
    return render_template("only_admins.html")


@user_bp.route("/only_approved")
def only_approved():
    return render_template("only_approved.html")


@user_bp.route("/users", endpoint="users")
@login_required
@admin_required
def users():
    all_users = User.get_all()
    all_buckets = list_buckets()
    all_groups = UserGroups.get_all_with_user_count()
    preapproved_users = PreapprovedUser.get_all()
    for bucket in all_buckets:
        Bucket.create(bucket)
    group_id = request.args.get("group_id")
    group_name = ""
    if group_id:
        group_id = int(group_id)  # Convert to integer if it's a string

        # Find the group name using the group_id from all_groups
        group_name = next(
            (group["name"] for group in all_groups if group["id"] == group_id),
            None,
        )

        if group_name:
            # Filter all_users to include only those in the specified group
            filtered_users = [
                user_info
                for user_info in all_users
                if group_name
                in user_info["user"].groups  # Assuming groups contains names
            ]
            all_users = filtered_users

    return render_template(
        "users.html",
        all_users=all_users,
        all_buckets=all_buckets,
        all_groups=all_groups,
        group_name=group_name,
        preapproved_users=preapproved_users,
    )


@user_bp.route("/user_groups", endpoint="user_groups")
@login_required
@admin_required
def user_groups():

    all_groups = UserGroups.get_all_with_user_count()
    return render_template("user_groups.html", all_groups=all_groups)


@user_bp.route("/add_user_group", methods=["POST"], endpoint="add_user_group")
@login_required
@admin_required
def add_user_group():
    group_name = request.form.get("name")
    UserGroups.create(group_name)

    return redirect(url_for("user.user_groups"))


@user_bp.route(
    "/update_admin_status", methods=["POST"], endpoint="update_admin_status"
)
@login_required
@admin_required
def update_admin_status():
    user_id = request.form.get("user_id")
    admin_status = request.form.get("admin") == "on"  # Convert to boolean
    # Update the admin status in the database based on user_id and admin_status
    User.update_admin_status(user_id, admin_status)
    return redirect("/users")


@user_bp.route(
    "/update_approved_status",
    methods=["POST"],
    endpoint="update_approved_status",
)
@login_required
@admin_required
def update_approved_status():
    user_id = request.form.get("user_id")
    approved_status = (
        request.form.get("approved") == "on"
    )  # Convert to boolean
    # Update the admin status in the database based on user_id and admin_status
    User.update_approved_status(user_id, approved_status)
    return redirect("/users")


@user_bp.route(
    "/give_access_to_bucket",
    methods=["POST"],
    endpoint="give_access_to_bucket",
)
@login_required
@admin_required
def give_access_to_bucket():
    user_id = request.form.get("user_id")
    bucket = request.form.get("bucket")
    User.add_user_bucket_access(user_id, bucket)

    return redirect("/users")


@user_bp.route(
    "/add_user_to_group",
    methods=["POST"],
    endpoint="add_user_to_group",
)
@login_required
@admin_required
def add_user_to_group():
    user_id = request.form.get("user_id")
    group = request.form.get("group")
    User.add_user_group_access(user_id, group)
    return redirect("/users")


@user_bp.route(
    "/remove_user_from_group",
    methods=["POST"],
    endpoint="remove_user_from_group",
)
@login_required
@admin_required
def remove_user_from_group():
    user_id = request.form.get("user_id")
    group = request.form.get("group")

    User.delete_user_group_access(user_id, group)
    if User.is_user_in_group_by_name(user_id, group):
        return {"status": 0}
    else:
        return {"status": 1}


@user_bp.route(
    "/remove_access_from_bucket",
    methods=["POST"],
    endpoint="remove_access_from_bucket",
)
@login_required
@admin_required
def remove_access_from_bucket():
    user_id = request.form.get("user_id")
    bucket = request.form.get("bucket")

    User.delete_user_bucket_access(user_id, bucket)
    if User.has_bucket_access(user_id, bucket):
        return {"status": 0}
    else:
        return {"status": 1}


@user_bp.route("/remove_user", methods=["POST"], endpoint="remove_user")
@login_required
@admin_required
def remove_user():
    user_id = request.form.get("user_id")

    user_delete_result = User.delete(user_id)
    return user_delete_result


@user_bp.route(
    "/add_preapproved_user", methods=["POST"], endpoint="add_preapproved_user"
)
@login_required
@admin_required
def add_preapproved_user():
    user_email = request.form.get("user_email")
    bucket = request.form.get("bucket")
    group_id = request.form.get("group")
    logger.info("The group is is " + str(group_id))
    PreapprovedUser.create(
        email=user_email,
        bucket=bucket,
        group_id=group_id,
    )

    return redirect(url_for("user.users"))
