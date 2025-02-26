import logging
import folium
from flask import Blueprint, render_template, request
from flask_login import current_user, login_required
from models.bucket import Bucket
from helpers.bucket import make_file_accessible
from helpers.statistics import (
    get_cohorts_data,
    get_samples_per_cohort_type_data,
)
from helpers.decorators import (
    admin_or_owner_required,
    approved_required,
    staff_required,
)

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
    data = get_samples_per_cohort_type_data()

    color_map = {
        "SpunLed": "red",
        "ThirdParty": "blue",
        "UE": "green",
        "Other": "gray",
    }

    m = folium.Map(location=[20, 0], zoom_start=2)
    feature_groups = {
        key: folium.FeatureGroup(name=key) for key in color_map.keys()
    }

    for item in data:
        lat, lon = item["Latitude"], item["Longitude"]
        cohort_group = item["cohort_group"]
        sample_id = item["SampleID"]
        project_id = item["project_id"]
        cohort = item["cohort"]  # Full cohort name if needed

        color = color_map.get(cohort_group, "gray")

        # Create a popup with additional information
        popup_text = f"""
        <b>Sample ID:</b> {sample_id}<br>
        <b>Project ID:</b> {project_id}<br>
        <b>Cohort:</b> {cohort}<br>
        <b>Cohort Group:</b> {cohort_group}
        """

        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300),
        )

        feature_groups[cohort_group].add_child(marker)

    for group in feature_groups.values():
        m.add_child(group)

    folium.LayerControl().add_to(m)

    # Save the map
    map_path = "static/map.html"
    m.save(map_path)

    return render_template("index.html")


@data_bp.route("/map/view", endpoint="show_map")
@login_required
@approved_required
@staff_required
def show_map():
    return render_template("map.html")
