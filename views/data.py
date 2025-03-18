import logging
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from models.bucket import Bucket
from helpers.bucket import make_file_accessible
from helpers.statistics import (
    get_cohorts_data,
)
from helpers.decorators import (
    admin_or_owner_required,
    approved_required,
    staff_required,
)
from helpers.maps import generate_samples_geojson

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

data_bp = Blueprint("data", __name__)


@data_bp.route("/data")
@login_required
def data():
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
@admin_or_owner_required
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
@admin_or_owner_required
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


@data_bp.route("/show_statistics", endpoint="show_statistics")
@login_required
@approved_required
@staff_required
def show_statistics():
    cohort_data = get_cohorts_data()
    return render_template("statistics.html", cohort_data=cohort_data)


@data_bp.route("/map/generate", endpoint="generate_map")
@login_required
@approved_required
@staff_required
def generate_map():
    generate_samples_geojson()

    return render_template("index.html")


@data_bp.route("/map/view", endpoint="show_map")
@login_required
@approved_required
@staff_required
def show_map():
    geojson_path = "/static/data.geojson"
    return render_template("map_dynamic.html", geojson_path=geojson_path)
