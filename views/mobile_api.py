import os
import uuid
import logging
from datetime import date
from functools import wraps

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from helpers.dbm import session_scope
from helpers.slack import send_message_to_slack_mobile
from models.db_model import (
    MobileAppProjectTable,
    MobileAppStagingSampleTable,
    MobileAppStagingPhotoTable,
)

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


@mobile_api_bp.route("/projects", methods=["POST"])
@_require_api_key
def upsert_project():
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

    project_id = str(body.get("project_id") or "").strip()
    name = str(body.get("name") or "").strip()
    submitter_id = str(body.get("submitter_id") or "").strip()

    missing = [
        f
        for f, v in [
            ("project_id", project_id),
            ("name", name),
            ("submitter_id", submitter_id),
        ]
        if not v
    ]
    if missing:
        return jsonify({"error": f"missing required fields: {missing}"}), 400

    with session_scope() as session:
        project = (
            session.query(MobileAppProjectTable)
            .filter_by(project_id=project_id)
            .first()
        )
        if project is None:
            session.add(
                MobileAppProjectTable(
                    project_id=project_id[:36],
                    name=name[:255],
                    submitter_id=submitter_id[:255],
                )
            )
            logger.info(
                "Mobile API: created project '%s' (uuid=%s) for submitter '%s'",
                name,
                project_id,
                submitter_id,
            )
            is_new = True
        else:
            project.name = name[:255]
            logger.info(
                "Mobile API: updated project name to '%s' (uuid=%s)",
                name,
                project_id,
            )
            is_new = False

    if is_new:
        send_message_to_slack_mobile(
            f"New mobile project created\n"
            f"*Project:* {name}\n"
            f"*Submitted by:* {submitter_id}"
        )

    return jsonify({"status": "ok"}), 200


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
                accuracy=sample.get("accuracy"),
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
    first_project_name = rows[0].project_name or rows[0].project_id

    with session_scope() as session:
        session.add_all(rows)

    logger.info(
        "Mobile API: inserted %d staging sample(s) from submitter '%s'",
        len(rows),
        first_submitter,
    )

    sample_lines = []
    for sample in samples:
        lat = sample.get("latitude")
        lon = sample.get("longitude")
        if lat is not None and lon is not None:
            coords = f"lat: {lat}, lon: {lon}"
        else:
            coords = "coordinates not provided"
        sample_lines.append(f"• {sample['sample_id']} — {coords}")

    send_message_to_slack_mobile(
        f"{len(rows)} new sample(s) uploaded from mobile app\n"
        f"*Project:* {first_project_name}\n"
        f"*Submitted by:* {first_submitter}\n" + "\n".join(sample_lines)
    )

    return jsonify({"inserted": len(rows)}), 200


@mobile_api_bp.route("/photos", methods=["POST"])
@_require_api_key
def upload_photo():
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto and forwarded_proto != "https":
        return jsonify({"error": "HTTPS required"}), 403

    sample_id = request.form.get("sample_id", "").strip()
    project_id = request.form.get("project_id", "").strip()
    submitter_id = request.form.get("submitter_id", "").strip()

    missing = [
        f
        for f, v in [
            ("sample_id", sample_id),
            ("project_id", project_id),
            ("submitter_id", submitter_id),
        ]
        if not v
    ]
    if missing:
        return jsonify({"error": f"missing required fields: {missing}"}), 400

    photo = request.files.get("photo")
    if photo is None:
        return jsonify({"error": "missing required field: photo"}), 400

    if not photo.content_type or not photo.content_type.startswith("image/"):
        return jsonify({"error": "uploaded file must be an image"}), 400

    with session_scope() as session:
        project = (
            session.query(MobileAppProjectTable)
            .filter_by(project_id=project_id)
            .first()
        )
        if project is None:
            return jsonify({"error": "project not found"}), 404
        numeric_project_id = project.id

    project_folder = f"{numeric_project_id:04d}"
    try:
        sample_folder = f"sample_{int(sample_id):06d}"
    except ValueError:
        sample_folder = f"sample_{secure_filename(sample_id)}"

    photos_dir = os.environ.get("MOBILE_PHOTOS_DIR", "mobile_app_photos")
    save_dir = os.path.join(photos_dir, project_folder, sample_folder)
    os.makedirs(save_dir, exist_ok=True)

    original_filename = secure_filename(photo.filename or "photo.jpg")
    unique_filename = f"{uuid.uuid4().hex}.jpg"
    file_path = os.path.join(save_dir, unique_filename)
    photo.save(file_path)

    with session_scope() as session:
        session.add(
            MobileAppStagingPhotoTable(
                sample_id=sample_id[:100],
                project_id=project_id[:36],
                submitter_id=submitter_id[:255],
                file_path=file_path,
                original_filename=original_filename,
            )
        )

    logger.info(
        "Mobile API: saved photo for sample '%s' (project %s -> %s) "
        "from submitter '%s' at '%s'",
        sample_id,
        project_id,
        project_folder,
        submitter_id,
        file_path,
    )
    return jsonify({"status": "ok"}), 200
