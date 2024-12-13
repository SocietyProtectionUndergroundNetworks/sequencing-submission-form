import logging
from flask import (
    redirect,
    Blueprint,
    render_template,
    request,
    url_for,
    jsonify,
)
from flask_login import current_user, login_required
from models.bucket import Bucket

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

bucket_bp = Blueprint("bucket", __name__)


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


@bucket_bp.route("/buckets", methods=["GET"], endpoint="buckets")
@admin_required
@login_required
def buckets():
    all_buckets = Bucket.get_all()

    return render_template(
        "buckets.html",
        all_buckets=all_buckets,
    )


@bucket_bp.route("/set_bucket_cohort", methods=["POST"])
@admin_required
@login_required
def set_bucket_cohort():
    data = request.get_json()
    bucket_id = data.get("id")
    new_cohort = data.get("cohort")

    if not bucket_id or new_cohort is None:
        return jsonify({"error": "Invalid data"}), 400

    logger.info("for bucket ")
    logger.info(bucket_id)
    logger.info("we will put the cohort ")
    logger.info(new_cohort)
    Bucket.update_cohort(bucket_id, new_cohort)
    return jsonify({"message": "Cohort updated successfully"})
