import logging
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
)
from flask_login import login_required
from models.bucket import Bucket
from helpers.decorators import (
    admin_required,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

bucket_bp = Blueprint("bucket", __name__)


@bucket_bp.route("/buckets", methods=["GET"], endpoint="buckets")
@admin_required
@login_required
def buckets():
    order_by = request.args.get("order_by", "name")
    all_buckets = Bucket.get_all(order_by)

    return render_template(
        "buckets.html", all_buckets=all_buckets, order_by=order_by
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
