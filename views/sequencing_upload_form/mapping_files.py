from . import upload_form_bp
import os
import logging
from flask_login import login_required
from flask import (
    redirect,
    request,
    url_for,
    jsonify,
    send_file,
)
from helpers.decorators import (
    approved_required,
    admin_required,
    admin_or_owner_required,
)
from models.sequencing_upload import SequencingUpload
from models.sequencing_files_uploaded import SequencingFileUploaded

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
    "/generate_mapping_files",
    methods=["POST"],
    endpoint="generate_mapping_files",
)
@login_required
@admin_required
@approved_required
def generate_mapping_files():
    process_id = request.form.get("process_id")
    mode = request.form.get("mode")
    SequencingUpload.generate_mapping_files_for_process(process_id, mode)
    SequencingUpload.export_sample_locations(process_id)
    return (
        jsonify({"result": 1}),
        200,
    )


@upload_form_bp.route(
    "/show_mapping_file", methods=["GET"], endpoint="show_mapping_file"
)
@login_required
@approved_required
@admin_or_owner_required
def show_mapping_file():
    process_id = request.args.get("process_id")
    region = request.args.get("region")

    # Fetch process data from SequencingUpload model
    process_data = SequencingUpload.get(process_id)

    # Extract uploads folder and project id from process data
    uploads_folder = process_data["uploads_folder"]

    if region in process_data["regions"]:
        mapping_file = os.path.join(
            "seq_processed",
            uploads_folder,
            "mapping_files",
            f"{region}_Mapping.txt",
        )
        abs_mapping_file = os.path.abspath(mapping_file)

        if os.path.isfile(abs_mapping_file):
            return send_file(abs_mapping_file, as_attachment=True)

    return []


@upload_form_bp.route(
    "/delete_mapping_file", methods=["GET"], endpoint="delete_mapping_file"
)
@login_required
@admin_required
@approved_required
def delete_mapping_file():
    process_id = request.args.get("process_id")
    region = request.args.get("region")

    # Fetch process data from SequencingUpload model
    process_data = SequencingUpload.get(process_id)

    # Extract uploads folder and project id from process data
    uploads_folder = process_data["uploads_folder"]

    if region in process_data["regions"]:
        mapping_file = os.path.join(
            "seq_processed",
            uploads_folder,
            "mapping_files",
            f"{region}_Mapping.txt",
        )
        abs_mapping_file = os.path.abspath(mapping_file)

        # Check if the file exists and delete it if it does
        if os.path.exists(abs_mapping_file):
            os.remove(abs_mapping_file)

    return redirect(
        url_for("upload_form_bp.metadata_form", process_id=process_id)
        + "#step_11"
    )


@upload_form_bp.route(
    "/exclude_from_mapping",
    methods=["POST"],
    endpoint="exclude_from_mapping",
)
@login_required
@approved_required
@admin_required
def exclude_from_mapping():
    data = request.get_json()
    file_id = data.get("file_id")
    exclude = data.get("exclude")

    SequencingFileUploaded.update_field(
        file_id, "exclude_from_mapping", exclude
    )
    return jsonify({"success": True, "file_id": file_id, "exclude": exclude})
