import logging
import os
import pandas as pd
from collections import defaultdict
from flask import redirect, Blueprint, render_template, request, url_for
from flask_login import current_user, login_required
from models.sequencing_company_upload import SequencingCompanyUpload
from models.sequencing_company_input import SequencingCompanyInput
from pathlib import Path

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

scripps_bp = Blueprint("scripps", __name__)


# Custom admin_required decorator
def admin_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for("user.only_admins"))
        return view_func(*args, **kwargs)

    return decorated_view


# Custom approved_required decorator
def approved_required(view_func):
    def decorated_approved_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(
                url_for("user.login")
            )  # Adjust 'login' to your actual login route
        elif not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for("user.only_approved"))
        return view_func(*args, **kwargs)

    return decorated_approved_view


@scripps_bp.route("/scripps_form", methods=["GET"], endpoint="scripps_form")
@admin_required
@login_required
def scripps_form():
    upload_id = request.args.get("upload_id", "")
    directory_name = request.args.get("directory_name", "")
    upload = {}
    input_lines = []
    report = []

    if upload_id:
        upload = SequencingCompanyUpload.get(upload_id)
        input_lines = SequencingCompanyInput.get_all_by_upload_id(upload_id)
        logger.info(upload)

        if directory_name:
            # Construct the full directory path and check for files
            full_directory_path = Path(directory_name)
            fastq_files = list(
                full_directory_path.glob("*.fastq.gz")
            )  # Look for .fastq.gz files

            # Now associate files with the input_lines
            # based on the Sequencer_ID
            for line in input_lines:
                sequencer_id = line.get("sequencer_id", "")
                if sequencer_id:
                    # Check if any of the files start with the sequencer ID
                    matching_files = [
                        f.name
                        for f in fastq_files
                        if f.name.startswith(sequencer_id)
                    ]

                    line["matching_files"] = (
                        matching_files  # Add matched files to the line
                    )

        # Existing logic for grouping the records and generating the report
        grouped_data = defaultdict(list)
        for line in input_lines:
            sequencer_exists = line.get("sequencer_exists", False)
            group_key = (
                line["project"],
                line["metadata_upload_id"],
                sequencer_exists,
            )
            grouped_data[group_key].append(line)

        report = []
        for (
            project,
            metadata_upload_id,
            sequencer_exists,
        ), records in grouped_data.items():
            total_records = len(records)
            matched_records = sum(
                1 for record in records if record["SampleID"] is not None
            )
            unmatched_records = total_records - matched_records
            report.append(
                {
                    "project": project,
                    "metadata_upload_id": metadata_upload_id,
                    "sequencer_exists": sequencer_exists,
                    "total": total_records,
                    "matched": matched_records,
                    "unmatched": unmatched_records,
                }
            )

    return render_template(
        "scripps_form.html",
        upload=upload,
        upload_id=upload_id,
        input_lines=input_lines,
        report=report,
        directory_name=directory_name,
    )


@scripps_bp.route(
    "/all_scripps_uploads", methods=["GET"], endpoint="all_scripps_uploads"
)
@login_required
@admin_required
@approved_required
def all_scripps_uploads():
    scripps_uploads = SequencingCompanyUpload.get_all()
    return render_template(
        "scripps_uploads.html", scripps_uploads=scripps_uploads
    )


@scripps_bp.route(
    "/scripps_upload_sequencing_file",
    methods=["POST"],
    endpoint="scripps_upload_sequencing_file",
)
@admin_required
@login_required
def scripps_upload_sequencing_file():
    file = request.files.get("file")
    upload_id = request.form.get("upload_id")  # Get upload_id from form data

    # Read uploaded file and get its column names
    filename = file.filename
    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == ".csv":
        df = pd.read_csv(file)

        # Define the expected columns and their mapping
        expected_columns = {
            "Sample Number": "sample_number",
            "Sample_ID": "sample_id",
            "Sequencer_ID": "sequencer_id",
            "Sequencing_provider": "sequencing_provider",
            "Project": "project",
            "Region": "region",
            "Index_1": "index_1",
            "Barcode_2": "barcode_2",
        }

        # Check if the columns in the file match the expected columns
        if not expected_columns.keys() <= set(df.columns):
            logger.error(f"CSV file has incorrect columns: {df.columns}")
            return {"error": "Invalid column names"}, 400

        df = df.dropna(how="all")
        # Replace NaN values with None for compatibility with MySQL
        df = df.where(pd.notnull(df), None)

        # Rename columns to match the expected database column names
        df.rename(columns=expected_columns, inplace=True)

        # Check for problems in the DataFrame
        df_with_problems = SequencingCompanyInput.check_dataframe(df)

        # Prepare the response data
        response_data = {
            "data": df_with_problems.to_dict(
                orient="records"
            ),  # Convert the DataFrame to a list of dicts
            "has_problems": df_with_problems["problems"]
            .notnull()
            .any()
            .tolist(),  # Convert boolean to a list
        }

        # If there are no problems, add the records to the database
        if not response_data["has_problems"]:

            # If an upload_id is provided, use it; otherwise,
            # create a new upload
            if upload_id:
                existing_upload = SequencingCompanyUpload.get(upload_id)
                if existing_upload:
                    # Update the existing upload's filename
                    SequencingCompanyUpload.update_field(
                        upload_id, "csv_filename", filename
                    )
                else:
                    logger.error("Upload ID does not exist")
                    return {"error": "Upload ID does not exist"}, 400
            else:
                upload_id = SequencingCompanyUpload.create(filename)

            for _, row in df_with_problems.iterrows():
                SequencingCompanyInput.create(upload_id, row.to_dict())

            return {
                "success": "Records added successfully",
                "upload_id": upload_id,
            }, 200

        # Return the response data with a status code of 200
        return (
            response_data,
            200,
        )  # Return data with problems, but status 200 for successful request

    return {
        "error": "Invalid file type"
    }, 400  # Return error if not a CSV file


@scripps_bp.route(
    "/move_sequencer_ids_to_project",
    methods=["POST"],
    endpoint="move_sequencer_ids_to_project",
)
@admin_required
@login_required
def move_sequencer_ids_to_project():
    upload_id = request.form.get("upload_id")
    metadata_upload_id = request.form.get("metadata_upload_id")

    SequencingCompanyInput.copy_sequencer_ids_to_metadata_upload(
        upload_id, metadata_upload_id
    )

    logger.info("upload_id: " + str(upload_id))
    logger.info("metadata_upload_id: " + str(metadata_upload_id))
    return (
        {"result": 1},
        200,
    )
