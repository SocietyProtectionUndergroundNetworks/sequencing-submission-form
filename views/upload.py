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
from models.user import User
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample
from helpers.decorators import (
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
