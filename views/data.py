import logging
from flask import Blueprint, render_template
from flask_login import login_required
from helpers.statistics import (
    get_cohorts_data,
)
from helpers.decorators import (
    approved_required,
    staff_required,
)
from helpers.maps import generate_samples_geojson

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

data_bp = Blueprint("data", __name__)


@data_bp.route("/show_statistics", endpoint="show_statistics")
@login_required
@approved_required
@staff_required
def show_statistics():
    cohort_data = get_cohorts_data()
    return render_template("statistics.html", cohort_data=cohort_data)


@data_bp.route("/data", endpoint="data")
@login_required
@approved_required
def data():
    return render_template("removed_functionality.html")


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
