import logging
from flask_login import login_required
from flask import Blueprint
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
