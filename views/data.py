import os
import logging
from flask import redirect, Blueprint, render_template, request
from flask_login import current_user, login_required
from models.user import User
from models.bucket import Bucket
from helpers.bucket import (
    make_file_accessible,
    download_bucket_contents,
    delete_buckets_archive_files,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

data_bp = Blueprint("data", __name__)


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


# Custom approved_required decorator
def approved_required(view_func):
    def decorated_approved_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for("user.only_approved"))
        return view_func(*args, **kwargs)

    return decorated_approved_view


@data_bp.route("/data")
@login_required
def data():
    all_buckets = Bucket.get_all()
    my_buckets = {}
    for my_bucket in current_user.buckets:
        my_buckets[my_bucket] = Bucket.get(my_bucket)

    return render_template("data.html", my_buckets=my_buckets)


@data_bp.route(
    "/generate_download_link",
    methods=["POST"],
    endpoint="generate_download_link",
)
@login_required
def generate_download_link():
    file = request.form.get("file")
    bucket = request.form.get("bucket")
    url = make_file_accessible(bucket, "archive/" + file)

    return {"status": 1, "url": url}


@data_bp.route(
    "/create_bucket_archive",
    methods=["POST"],
    endpoint="create_bucket_archive",
)
@login_required
@approved_required
def create_bucket_archive():
    from tasks import download_bucket_contents_async

    bucket = request.form.get("bucket")
    download_bucket_contents_async.delay(bucket)
    return {"status": 1, "message": "Process started"}


@data_bp.route("/get_archive_progress", endpoint="get_archive_progress")
@login_required
@approved_required
def get_archive_progress():
    bucket = request.args.get("bucket")
    this_bucket = Bucket.get(bucket)
    progress = this_bucket.archive_file_creation_progress
    if (progress is not None) and (progress >= 100):
        file = this_bucket.archive_file
        url = make_file_accessible(bucket, "archive/" + file)
        return {"progress": progress, "url": url}
    else:
        return {"progress": progress}
