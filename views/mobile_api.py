import os
import logging
from datetime import date
from functools import wraps

from flask import Blueprint, request, jsonify
from helpers.dbm import session_scope
from models.db_model import MobileAppStagingSampleTable

logger = logging.getLogger("my_app_logger")

mobile_api_bp = Blueprint("mobile_api", __name__, url_prefix="/api")

_REQUIRED_FIELDS = {
    "sample_id",
    "project_id",
    "submitter_id",
    "date_collected",
}


def _require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = os.environ.get("MOBILE_API_KEY")
        if not api_key:
            logger.error(
                "MOBILE_API_KEY environment variable is not configured"
            )
            return jsonify({"error": "API key not configured on server"}), 500

        provided = request.headers.get("X-API-Key", "")
        if not provided or provided != api_key:
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated


@mobile_api_bp.route("/samples/batch", methods=["POST"])
@_require_api_key
def batch_submit_samples():
    # Nginx sets X-Forwarded-Proto; reject plain HTTP in production
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto and forwarded_proto != "https":
        return jsonify({"error": "HTTPS required"}), 403

    if (
        not request.content_type
        or "application/json" not in request.content_type
    ):
        return jsonify({"error": "Content-Type must be application/json"}), 415

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    samples = body.get("samples")
    if not isinstance(samples, list) or len(samples) == 0:
        return jsonify({"error": "'samples' must be a non-empty array"}), 400

    rows = []
    errors = []

    for i, sample in enumerate(samples):
        missing = _REQUIRED_FIELDS - set(sample.keys())
        if missing:
            errors.append(
                {
                    "index": i,
                    "error": f"missing required fields: {sorted(missing)}",
                }
            )
            continue

        try:
            collected = date.fromisoformat(str(sample["date_collected"]))
        except (ValueError, TypeError):
            errors.append(
                {
                    "index": i,
                    "error": "date_collected must be in YYYY-MM-DD format",
                }
            )
            continue

        rows.append(
            MobileAppStagingSampleTable(
                sample_id=str(sample["sample_id"])[:100],
                project_id=str(sample["project_id"])[:36],
                project_name=sample.get("project_name"),
                submitter_id=str(sample["submitter_id"])[:255],
                date_collected=collected,
                latitude=sample.get("latitude"),
                longitude=sample.get("longitude"),
                elevation=sample.get("elevation"),
                sample_type=sample.get("sample_type"),
                sample_or_control=sample.get(
                    "sample_or_control", "True sample"
                ),
                transport=sample.get("transport"),
                drying=sample.get("drying"),
                soil_depth=sample.get("soil_depth"),
                grid_size=sample.get("grid_size"),
                land_use=sample.get("land_use"),
                agricultural=sample.get("agricultural"),
                vegetation=sample.get("vegetation"),
                notes=sample.get("notes"),
                dna_concentration_ng_ul=sample.get("dna_concentration_ng_ul"),
            )
        )

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    first_submitter = samples[0].get("submitter_id", "unknown")

    with session_scope() as session:
        session.add_all(rows)

    logger.info(
        "Mobile API: inserted %d staging sample(s) from submitter '%s'",
        len(rows),
        first_submitter,
    )
    return jsonify({"inserted": len(rows)}), 200
