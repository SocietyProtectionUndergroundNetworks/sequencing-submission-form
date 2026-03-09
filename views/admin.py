import logging
import psutil
from flask_login import (
    current_user,
    login_required,
)
from flask import (
    Blueprint,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    request,
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
from models.sequencing_upload import SequencingUpload
from models.app_configuration import AppConfiguration
from helpers.hetzner_vm import list_existing_vms

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


@admin_bp.route(
    "/admin_operations",
    methods=["GET"],
    endpoint="admin_operations",
)
@login_required
@admin_required
@approved_required
def admin_operations():
    if current_user.is_authenticated:

        sys_info = {}
        if current_user.admin:
            disk_usage = psutil.disk_usage("/app")
            sys_info["disk_used_percent"] = disk_usage.percent

        samples_with_missing_fields_nr = 0
        if current_user.admin:
            samples_with_missing_fields_nr = (
                SequencingSample.count_missing_fields()
            )

        return render_template(
            "admin_operations.html",
            name=current_user.name,
            user_id=current_user.id,
            email=current_user.email,
            sys_info=sys_info,
            samples_with_missing_fields_nr=samples_with_missing_fields_nr,
        )
    else:
        return render_template("public_homepage.html")


@admin_bp.route(
    "/admin/lotus_and_scripts",
    methods=["GET"],
    endpoint="lotus_and_scripts",
)
@login_required
@admin_required
@approved_required
def lotus_and_scripts():
    return render_template("lotus_and_rscripts_nuke.html")


@admin_bp.route(
    "/admin/storage_per_project",
    methods=["GET"],
    endpoint="storage_per_project",
)
@login_required
@admin_required
@approved_required
def storage_per_project():
    all_uploads = SequencingUpload.get_all()
    return render_template(
        "project_bucket_admin.html",
        all_uploads=all_uploads,
    )


@admin_bp.route(
    "/admin/configuration",
    methods=["GET"],
    endpoint="configuration",
)
@login_required
@admin_required
@approved_required
def configuration():
    all_config = AppConfiguration.get_all()
    return render_template(
        "configuration.html",
        all_config=all_config,
    )


@admin_bp.route("/admin/configuration/update", methods=["POST"])
@login_required
@admin_required
@approved_required
def update_configuration():
    remote_pipeline_value = request.form.get("remote_pipeline")

    AppConfiguration.update_config("remote_pipeline", remote_pipeline_value)

    flash("Configuration updated successfully!", "success")
    return redirect(url_for("admin.configuration"))


@admin_bp.route(
    "/admin/see_vms",
    methods=["GET"],
    endpoint="see_vms",
)
@login_required
@admin_required
@approved_required
def see_vms():
    vms = list_existing_vms()
    return render_template("see_vms.html", vms=vms)
