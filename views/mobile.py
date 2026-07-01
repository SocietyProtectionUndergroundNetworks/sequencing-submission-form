import base64
import json
import os
import smtplib
import logging
from email.message import EmailMessage

import anthropic as anthropic_sdk
from flask import (
    Blueprint,
    jsonify,
    request,
    render_template,
    abort,
    send_file,
    redirect,
    url_for,
)
from flask_login import login_required
from helpers.slack import send_message_to_slack
from helpers.dbm import session_scope
from helpers.decorators import (
    approved_required,
    staff_required,
    admin_required,
)
from models.db_model import (
    MobileAppProjectTable,
    MobileAppStagingSampleTable,
    MobileAppStagingPhotoTable,
)

logger = logging.getLogger("my_app_logger")

mobile_bp = Blueprint("mobile", __name__, url_prefix="/mobile")


def _send_deletion_request_email(requester_email, admin_email):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not admin_email:
        logger.warning(
            "SMTP_HOST or ADMIN_CONTACT_EMAIL not configured — skipping email"
        )
        return

    msg = EmailMessage()
    msg["Subject"] = "Account Deletion Request — SPUN Field App"
    msg["From"] = smtp_from
    msg["To"] = admin_email
    msg.set_content(
        f"A user has submitted an account deletion request via the SPUN Field mobile app.\n\n"
        f"Email address: {requester_email}\n\n"
        f"Please process this request according to your data deletion policy."
    )

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)


@mobile_bp.route("/projects", methods=["GET"])
@login_required
@staff_required
@approved_required
def mobile_projects_list():
    with session_scope() as session:
        projects = (
            session.query(MobileAppProjectTable)
            .order_by(MobileAppProjectTable.created_at.desc())
            .all()
        )
        projects_data = [
            {
                "id": p.id,
                "project_id": p.project_id,
                "name": p.name,
                "submitter_id": p.submitter_id,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in projects
        ]
    return render_template("mobile_projects_list.html", projects=projects_data)


@mobile_bp.route("/projects/<int:project_id>", methods=["GET"])
@login_required
@staff_required
@approved_required
def mobile_project_detail(project_id):
    with session_scope() as session:
        project = (
            session.query(MobileAppProjectTable)
            .filter_by(id=project_id)
            .first()
        )
        if project is None:
            abort(404)
        project_data = {
            "id": project.id,
            "project_id": project.project_id,
            "name": project.name,
            "submitter_id": project.submitter_id,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }
        samples = (
            session.query(MobileAppStagingSampleTable)
            .filter_by(project_id=project_id)
            .order_by(MobileAppStagingSampleTable.date_collected.desc())
            .all()
        )
        samples_data = []
        for s in samples:
            photos = (
                session.query(MobileAppStagingPhotoTable)
                .filter_by(sample_id=s.sample_id, project_id=project_id)
                .all()
            )
            samples_data.append(
                {
                    "id": s.id,
                    "sample_id": s.sample_id,
                    "submitter_id": s.submitter_id,
                    "date_collected": s.date_collected,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "elevation": s.elevation,
                    "sample_type": s.sample_type,
                    "sample_or_control": s.sample_or_control,
                    "transport": s.transport,
                    "drying": s.drying,
                    "soil_depth": s.soil_depth,
                    "grid_size": s.grid_size,
                    "land_use": s.land_use,
                    "agricultural": s.agricultural,
                    "vegetation": s.vegetation,
                    "notes": s.notes,
                    "dna_concentration_ng_ul": s.dna_concentration_ng_ul,
                    "received_at": s.received_at,
                    "photos": [
                        {
                            "id": ph.id,
                            "original_filename": ph.original_filename,
                            "received_at": ph.received_at,
                            "coords_extracted": bool(ph.coords_extracted),
                        }
                        for ph in photos
                    ],
                }
            )
    return render_template(
        "mobile_project_detail.html",
        project=project_data,
        samples=samples_data,
    )


@mobile_bp.route("/photos/<int:photo_id>", methods=["GET"])
@login_required
@staff_required
@approved_required
def mobile_photo(photo_id):
    with session_scope() as session:
        photo = (
            session.query(MobileAppStagingPhotoTable)
            .filter_by(id=photo_id)
            .first()
        )
        if photo is None:
            abort(404)
        file_path = photo.file_path
    return send_file(os.path.abspath(file_path))


@mobile_bp.route("/photos/<int:photo_id>/thumbnail", methods=["GET"])
@login_required
@staff_required
@approved_required
def mobile_photo_thumbnail(photo_id):
    with session_scope() as session:
        photo = (
            session.query(MobileAppStagingPhotoTable)
            .filter_by(id=photo_id)
            .first()
        )
        if photo is None:
            abort(404)
        file_path = photo.file_path

    abs_path = os.path.abspath(file_path)
    photo_dir = os.path.dirname(abs_path)
    thumb_dir = os.path.join(photo_dir, "thumbnails")
    thumb_path = os.path.join(thumb_dir, os.path.basename(abs_path))

    if not os.path.exists(thumb_path):
        from PIL import Image

        os.makedirs(thumb_dir, exist_ok=True)
        with Image.open(abs_path) as img:
            img = img.convert("RGB")
            img.thumbnail((240, 240))
            img.save(thumb_path, "JPEG", quality=75)

    return send_file(thumb_path, mimetype="image/jpeg")


@mobile_bp.route("/delete_account_request_form", methods=["GET", "POST"])
def delete_account_request_form():
    success = False
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            error = "Please enter your email address."
        else:
            admin_email = os.environ.get("ADMIN_CONTACT_EMAIL", "")

            try:
                send_message_to_slack(
                    f"Account deletion request received from: {email}"
                )
            except Exception:
                logger.exception(
                    "Failed to send Slack notification for deletion request from %s",
                    email,
                )

            try:
                _send_deletion_request_email(email, admin_email)
            except Exception:
                logger.exception(
                    "Failed to send email for deletion request from %s", email
                )
                error = (
                    "Your request was received but we could not send a "
                    "confirmation email. Please contact us directly at "
                    f"{admin_email}."
                )

            if not error:
                success = True

    return render_template(
        "mobile_delete_account_request.html",
        success=success,
        error=error,
    )


@mobile_bp.route("/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
@admin_required
def mobile_photo_delete(photo_id):
    with session_scope() as session:
        photo = (
            session.query(MobileAppStagingPhotoTable)
            .filter_by(id=photo_id)
            .first()
        )
        if photo is None:
            abort(404)
        project_id = photo.project_id
        file_path = photo.file_path
        session.delete(photo)

    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    thumb_path = os.path.join(
        os.path.dirname(abs_path), "thumbnails", os.path.basename(abs_path)
    )
    if os.path.exists(thumb_path):
        os.remove(thumb_path)

    logger.info("Admin deleted photo %d (file: %s)", photo_id, file_path)
    return redirect(
        url_for("mobile.mobile_project_detail", project_id=project_id)
    )


@mobile_bp.route("/photos/<int:photo_id>/extract_coords", methods=["POST"])
@login_required
@admin_required
def mobile_photo_extract_coords(photo_id):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            jsonify({"error": "ANTHROPIC_API_KEY not configured on server"}),
            500,
        )

    with session_scope() as session:
        photo = (
            session.query(MobileAppStagingPhotoTable)
            .filter_by(id=photo_id)
            .first()
        )
        if photo is None:
            abort(404)
        file_path = photo.file_path

    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return jsonify({"error": "Photo file not found on disk"}), 404

    with open(abs_path, "rb") as f:
        photo_bytes = f.read()

    image_data = base64.standard_b64encode(photo_bytes).decode("utf-8")

    client = anthropic_sdk.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=256,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This photo shows a GPS device display. "
                            "Extract the GPS coordinates visible on the screen. "
                            "Return ONLY a JSON object with three keys: "
                            "'raw' (the exact coordinate text as it appears on the screen, e.g. \"N 41°36.7141' E 001°54.3456'\"), "
                            "'latitude' (decimal degrees float, positive = North), "
                            "'longitude' (decimal degrees float, positive = East). "
                            "If the coordinates are in degrees/minutes/seconds or degrees/decimal-minutes format, convert to decimal degrees. "
                            'If you cannot read coordinates clearly, return {"error": "could not extract coordinates"}. '
                            "Return nothing else — just the JSON object."
                        ),
                    },
                ],
            }
        ],
    )

    raw_text = next(
        (block.text for block in message.content if hasattr(block, "text")),
        "",
    ).strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        import re

        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                result = {"error": f"Could not parse response: {raw_text}"}
        else:
            result = {"error": f"Unexpected response: {raw_text}"}

    if "error" not in result:
        with session_scope() as session:
            photo = (
                session.query(MobileAppStagingPhotoTable)
                .filter_by(id=photo_id)
                .first()
            )
            if photo:
                photo.coords_extracted = True

    logger.info("GPS extraction for photo %d: %s", photo_id, result)
    return jsonify(result)


@mobile_bp.route("/samples/<int:sample_id>/update_coords", methods=["POST"])
@login_required
@admin_required
def mobile_sample_update_coords(sample_id):
    try:
        latitude = float(request.form["latitude"])
        longitude = float(request.form["longitude"])
    except (KeyError, ValueError, TypeError):
        abort(400)

    with session_scope() as session:
        sample = (
            session.query(MobileAppStagingSampleTable)
            .filter_by(id=sample_id)
            .first()
        )
        if sample is None:
            abort(404)
        project_id = sample.project_id
        sample.latitude = latitude
        sample.longitude = longitude

    logger.info(
        "Staff updated coords for sample pk=%d: lat=%s, lon=%s",
        sample_id,
        latitude,
        longitude,
    )
    return redirect(
        url_for("mobile.mobile_project_detail", project_id=project_id)
    )
