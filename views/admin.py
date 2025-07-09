import logging
import psutil
from flask_login import (
    current_user,
    login_required,
)
from flask import (
    Blueprint,
    jsonify,
)
from helpers.decorators import (
    approved_required,
    admin_required,
)
from helpers.ecoregions import (
    import_ecoregions_from_csv,
    import_ecoregions_from_csv_its,
    import_ecoregions_from_csv_ssu,
    init_update_external_samples_with_ecoregions,
)
from models.sequencing_sample import SequencingSample

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

admin_bp = Blueprint("admin", __name__)


@admin_bp.route(
    "/run_import_ecoregions_from_csv",
    methods=["GET"],
    endpoint="run_import_ecoregions_from_csv",
)
@login_required
@approved_required
@admin_required
def run_import_ecoregions_from_csv():
    import_ecoregions_from_csv(
        "temp/Resolve_Ecoregions_-2451418960243700221.csv"
    )
    return {}


@admin_bp.route(
    "/run_import_external_samples_from_csv_its",
    methods=["GET"],
    endpoint="run_import_external_samples_from_csv_its",
)
@login_required
@approved_required
@admin_required
def run_import_external_samples_from_csv_its():
    import_ecoregions_from_csv_its("temp/external_samples_its.csv")
    return {}


@admin_bp.route(
    "/run_import_external_samples_from_csv_ssu",
    methods=["GET"],
    endpoint="run_import_external_samples_from_csv_ssu",
)
@login_required
@approved_required
@admin_required
def run_import_external_samples_from_csv_ssu():
    import_ecoregions_from_csv_ssu("temp/external_samples_ssu.csv")
    return {}


@admin_bp.route(
    "/run_update_external_samples_with_ecoregions",
    methods=["GET"],
    endpoint="run_update_external_samples_with_ecoregions",
)
@login_required
@approved_required
@admin_required
def run_update_external_samples_with_ecoregions():
    init_update_external_samples_with_ecoregions()
    return {}


@admin_bp.route("/sysreport", methods=["GET"], endpoint="show_system_report")
@login_required
@approved_required
def show_system_report():
    if current_user.admin:
        disk_usage = psutil.disk_usage("/app")
        return jsonify(
            {
                "total": disk_usage.total,
                "used": disk_usage.used,
                "free": disk_usage.free,
                "percent": disk_usage.percent,
            }
        )
    return {}


@admin_bp.route(
    "/update_missing_geo_data",
    methods=["GET"],
    endpoint="update_missing_geo_data",
)
@login_required
@admin_required
@approved_required
def update_missing_geo_data():

    SequencingSample.update_missing_fields()
    # land_use = get_land_use(-122.4194, 37.7749)
    # resolve_ecoregion = get_resolve_ecoregion(-122.4194, 37.7749)
    # baileys_ecoregion = get_baileys_ecoregion(-122.4194, 37.7749)
    # elevation = get_elevation(-122.4194, 37.7749)
    return jsonify({"done": 1}), 200
