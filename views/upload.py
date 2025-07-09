import logging
import psutil
from flask import (
    Blueprint,
    render_template,
    jsonify,
    redirect,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
)
from helpers.ecoregions import (
    import_ecoregions_from_csv,
    return_ecoregion,
    import_ecoregions_from_csv_its,
    import_ecoregions_from_csv_ssu,
    init_update_external_samples_with_ecoregions,
)
from models.user import User
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample
from helpers.decorators import (
    admin_required,
    approved_required,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/")
def index():
    if current_user.is_authenticated:
        if not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for("user.only_approved"))

        sys_info = {}
        if current_user.admin:
            disk_usage = psutil.disk_usage("/app")
            sys_info["disk_used_percent"] = disk_usage.percent

        user_metadata_uploads = SequencingUpload.get_by_user_id(
            current_user.id
        )
        user_groups = User.get_user_groups(current_user.id)

        user_should_see_v2 = False
        logger.info(user_groups)
        samples_with_missing_fields_nr = 0
        if current_user.admin:
            samples_with_missing_fields_nr = (
                SequencingSample.count_missing_fields()
            )

        for group in user_groups:
            if group["version"] == 2:
                user_should_see_v2 = True
                break  # No need to check further, since we found a match

        return render_template(
            "index.html",
            name=current_user.name,
            user_id=current_user.id,
            email=current_user.email,
            sys_info=sys_info,
            user_groups=user_groups,
            user_should_see_v2=user_should_see_v2,
            user_metadata_uploads=user_metadata_uploads,
            samples_with_missing_fields_nr=samples_with_missing_fields_nr,
        )
    else:
        return render_template("public_homepage.html")


@upload_bp.route("/privacy_and_terms", endpoint="privacy_and_terms")
def privacy_and_terms():
    return render_template("privacy_and_terms.html")


@upload_bp.route("/app_instructions", endpoint="app_instructions")
def app_instructions():
    # leaving it here for legacy.
    return render_template("app_instructions_v2.html")


@upload_bp.route("/app_instructions_v2", endpoint="app_instructions_v2")
def app_instructions_v2():
    return render_template("app_instructions_v2.html")


@upload_bp.route(
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


@upload_bp.route(
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


@upload_bp.route(
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


@upload_bp.route(
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


@upload_bp.route(
    "/test_resolve_ecoregion",
    methods=["GET"],
    endpoint="test_resolve_ecoregion",
)
@login_required
@approved_required
@admin_required
def test_resolve_ecoregion():
    coordinates_list = [(45.43, -73.94), (50.47, -104.37)]
    result = return_ecoregion(coordinates_list)
    return jsonify({"result": result}), 200


@upload_bp.route("/sysreport", methods=["GET"], endpoint="show_system_report")
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
