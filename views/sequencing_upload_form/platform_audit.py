import logging
from . import upload_form_bp
from flask_login import login_required
from flask import request, jsonify
from helpers.decorators import (
    approved_required,
    admin_required,
)
from helpers.platform_detection import audit_upload_platform

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
    "/audit_sequencing_platform",
    methods=["POST"],
    endpoint="audit_sequencing_platform",
)
@login_required
@admin_required
@approved_required
def audit_sequencing_platform():
    process_id = request.form.get("process_id")

    result = audit_upload_platform(process_id)
    if result is None:
        return jsonify({"error": "Upload not found."}), 404

    return jsonify(result)
