from . import upload_form_bp
import logging
import os
from flask_login import login_required
from flask import (
    redirect,
    request,
    url_for,
    send_file,
)
from helpers.decorators import (
    approved_required,
    admin_required,
)
from helpers.r_scripts import (
    create_pdf_report,
)
from models.sequencing_upload import SequencingUpload

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
    "/start_sync_process",
    methods=["GET"],
    endpoint="start_sync_process",
)
@login_required
@approved_required
@admin_required
def start_sync_process():
    process_id = request.args.get("process_id")
    # sync to the external share service
    from helpers.share_directory import init_sync_project

    init_sync_project(process_id)
    return redirect(
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_14"
    )


@upload_form_bp.route(
    "/create_share_link",
    methods=["GET"],
    endpoint="create_share_link",
)
@login_required
@approved_required
@admin_required
def create_share_link():
    process_id = request.args.get("process_id")
    process_data = SequencingUpload.get(process_id)
    project_id = process_data["project_id"]

    # sync to the external share service
    from helpers.share_directory import create_share

    # create the share link
    share_url = create_share(
        "seq_processed/" + process_data["uploads_folder"] + "/share",
        project_id,
    )
    if share_url:
        logger.info("The share url is " + share_url)
        SequencingUpload.update_field(process_id, "share_url", share_url)
    else:
        logger.info("The share url could not be returned")

    return redirect(
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_14"
    )


@upload_form_bp.route(
    "/prepare_pdf_report",
    methods=["GET"],
    endpoint="prepare_pdf_report",
)
@login_required
@admin_required
@approved_required
def prepare_pdf_report():
    process_id = request.args.get("process_id")
    create_pdf_report(process_id)
    return redirect(
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_14"
    )


@upload_form_bp.route(
    "/download_pdf_report",
    methods=["GET"],
    endpoint="download_pdf_report",
)
@login_required
@admin_required
@approved_required
def download_pdf_report():
    process_id = request.args.get("process_id")
    process_data = SequencingUpload.get(process_id)
    uploads_folder = process_data["uploads_folder"]

    pdf_report = os.path.join(
        "seq_processed",
        uploads_folder,
        "r_output",
        "report.pdf",
    )
    abs_pdf_report = os.path.abspath(pdf_report)

    if os.path.isfile(abs_pdf_report):
        return send_file(abs_pdf_report, as_attachment=True)

    return []
