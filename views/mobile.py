import os
import smtplib
import logging
from email.message import EmailMessage

from flask import (
    Blueprint,
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
