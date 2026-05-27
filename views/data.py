import csv
import io
import logging
from flask import Blueprint, render_template, send_file
from flask_login import login_required
from helpers.statistics import (
    get_cohorts_data,
    get_samples_per_cohort_type_data,
)
from helpers.decorators import (
    approved_required,
    staff_required,
)
from helpers.maps import generate_samples_geojson
from helpers.dbm import session_scope
from models.db_model import ExternalSamplingTable

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


@data_bp.route("/map/all_sample_csv", endpoint="all_sample_csv")
@login_required
@approved_required
@staff_required
def all_sample_csv():
    cohort_rows = get_samples_per_cohort_type_data()

    with session_scope() as session:
        external_rows = session.query(ExternalSamplingTable).all()
        external_data = [
            {
                "sample_id": r.sample_id,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "dna_region": r.dna_region,
            }
            for r in external_rows
            if r.latitude and r.longitude
        ]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "type",
            "SampleID",
            "Latitude",
            "Longitude",
            "project_id",
            "cohort",
            "cohort_group",
            "dna_region",
        ]
    )
    for row in cohort_rows:
        writer.writerow(
            [
                "cohort",
                row["SampleID"],
                row["Latitude"],
                row["Longitude"],
                row["project_id"],
                row["cohort"],
                row["cohort_group"],
                "",
            ]
        )
    for row in external_data:
        writer.writerow(
            [
                "external",
                row["sample_id"] or "",
                row["latitude"],
                row["longitude"],
                "",
                "",
                "",
                row["dna_region"] or "",
            ]
        )

    buf.seek(0)
    bytes_buf = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(
        bytes_buf,
        as_attachment=True,
        download_name="all_samples.csv",
        mimetype="text/csv",
    )


@data_bp.route("/data/export/gpkg", endpoint="export_gpkg")
@login_required
@approved_required
@staff_required
def export_gpkg():
    from helpers.gpkg import create_samples_gpkg

    buf = create_samples_gpkg()
    if buf is None:
        return {"error": "Failed to create GPKG file"}, 500

    return send_file(
        buf,
        as_attachment=True,
        download_name="samples.gpkg",
        mimetype="application/geopackage+sqlite3",
    )
