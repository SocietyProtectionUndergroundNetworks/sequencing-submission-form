import os
import smtplib
import logging
from email.message import EmailMessage

from flask import Blueprint, request, render_template
from helpers.slack import send_message_to_slack

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
