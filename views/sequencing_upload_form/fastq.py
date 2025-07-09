import shutil
import os
from . import upload_form_bp
from flask_login import login_required
from flask import (
    redirect,
    request,
    url_for,
    send_file,
)
from helpers.decorators import (
    admin_or_owner_required,
    approved_required,
    admin_required,
)
from helpers.fastqc import (
    init_create_multiqc_report,
)
from models.sequencing_files_uploaded import SequencingFileUploaded
from models.sequencing_upload import SequencingUpload


@upload_form_bp.route(
    "/show_fastqc_report", methods=["GET"], endpoint="show_fastqc_report"
)
@login_required
@approved_required
def show_fastqc_report():
    file_id = request.args.get("file_id")

    fastqc_report = SequencingFileUploaded.get_fastqc_report(file_id)

    if fastqc_report:
        return send_file(fastqc_report)

    return []


@upload_form_bp.route(
    "/generate_multiqc_report",
    methods=["POST"],
    endpoint="generate_multiqc_report",
)
@login_required
@admin_required
@approved_required
def generate_multiqc_report():
    process_id = request.form.get("process_id")
    init_create_multiqc_report(process_id)
    return []


@upload_form_bp.route(
    "/delete_multiqc_report", methods=["GET"], endpoint="delete_multiqc_report"
)
@login_required
@admin_required
@approved_required
def delete_multiqc_report():
    process_id = request.args.get("process_id")
    region = request.args.get("region")

    # Fetch process data from SequencingUpload model
    process_data = SequencingUpload.get(process_id)

    # Extract uploads folder and project id from process data
    uploads_folder = process_data["uploads_folder"]
    bucket = process_data["project_id"]

    if region in process_data["regions"]:
        multiqc_folder = os.path.join(
            "seq_processed", uploads_folder, "fastqc", bucket, region
        )

        # Remove the html file
        multiqc_file = os.path.join(
            multiqc_folder,
            "multiqc_report.html",
        )
        abs_html_file = os.path.abspath(multiqc_file)
        if os.path.isfile(abs_html_file):
            os.remove(abs_html_file)

        # Remove the data folder
        multiqc_data_folder = os.path.join(
            multiqc_folder,
            "multiqc_data",
        )
        abs_multiqc_data_folder = os.path.abspath(multiqc_data_folder)

        if os.path.isdir(abs_multiqc_data_folder):
            shutil.rmtree(abs_multiqc_data_folder)

        # Remove the plots folder
        multiqc_plots_folder = os.path.join(
            multiqc_folder,
            "multiqc_plots",
        )
        abs_multiqc_plots_folder = os.path.abspath(multiqc_plots_folder)

        if os.path.isdir(abs_multiqc_plots_folder):
            shutil.rmtree(abs_multiqc_plots_folder)

    return redirect(
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_10"
    )


@upload_form_bp.route(
    "/show_multiqc_report", methods=["GET"], endpoint="show_multiqc_report"
)
@login_required
@approved_required
@admin_or_owner_required
def show_multiqc_report():
    process_id = request.args.get("process_id")
    region = request.args.get("region")

    # Fetch process data from SequencingUpload model
    process_data = SequencingUpload.get(process_id)

    # Extract uploads folder and project id from process data
    uploads_folder = process_data["uploads_folder"]

    if region in process_data["regions"]:
        multiqc_file = os.path.join(
            "seq_processed",
            uploads_folder,
            "fastqc",
            region,
            "multiqc_report.html",
        )
        abs_html_file = os.path.abspath(multiqc_file)

        if os.path.isfile(abs_html_file):
            return send_file(abs_html_file)

    return []


@upload_form_bp.route(
    "/generate_fastqc_reports",
    methods=["POST"],
    endpoint="generate_fastqc_reports",
)
@login_required
@admin_required
@approved_required
def generate_fastqc_reports():
    process_id = request.form.get("process_id")
    SequencingUpload.ensure_fastqc_reports(process_id)
    return []
