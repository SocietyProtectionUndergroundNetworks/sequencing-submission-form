import logging
import pandas as pd
import os
import json
import csv
import shutil
from flask import (
    redirect,
    Blueprint,
    render_template,
    request,
    url_for,
    jsonify,
    send_file,
    Response,
)
from flask_login import current_user, login_required
from sqlalchemy.inspection import inspect
from models.bucket import Bucket
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample
from models.sequencing_sequencer_ids import SequencingSequencerId
from models.sequencing_files_uploaded import SequencingFileUploaded
from models.sequencing_analysis import SequencingAnalysis
from models.user import User
from helpers.metadata_check import (
    check_metadata,
    get_columns_data,
    get_project_common_data,
    sanitize_data,
    get_primer_sets_regions,
    primers_forward_to_reverse,
)
from helpers.create_xls_template import (
    create_template_one_drive_and_excel,
)
from helpers.bucket import (
    delete_bucket_folder,
    init_bucket_chunked_upload_v2,
    calculate_md5,
)
from helpers.fastqc import (
    init_create_fastqc_report,
    init_create_multiqc_report,
    check_multiqc_report,
)
import numpy as np
from helpers.lotus2 import (
    init_generate_lotus2_report,
    delete_generated_lotus2_report,
    init_generate_all_lotus2_reports,
)
from helpers.r_scripts import (
    init_generate_rscripts_report,
    delete_generated_rscripts_report,
    create_pdf_report,
)
from helpers.decorators import (
    admin_or_owner_required,
    approved_required,
    admin_required,
)


from pathlib import Path

metadata_bp = Blueprint("metadata", __name__)

logger = logging.getLogger("my_app_logger")


def process_uploaded_file(
    process_id,
    source_directory,
    filename,
    expected_md5,
    process_data,
    sequencing_run=None,
):
    uploads_folder = process_data["uploads_folder"]
    final_file_path = f"{source_directory}/{filename}"

    # Save into the database the file
    matching_sequencer_ids = SequencingSequencerId.get_matching_sequencer_ids(
        process_id, filename, sequencing_run
    )
    # Assign the file to the correct sequencer in
    # the database and process it further
    if len(matching_sequencer_ids) == 1:
        file_sequencer_id = matching_sequencer_ids[0]

        new_filename = SequencingSequencerId.generate_new_filename(
            process_id, filename
        )
        file_dict = {
            "md5": expected_md5,
            "original_filename": filename,
            "new_name": new_filename,
        }

        # Check if the file already exists before creating a new one
        existing_file_id = SequencingFileUploaded.check_if_exists(
            file_sequencer_id, file_dict
        )

        if existing_file_id:
            return None  # File already exists, return None to skip processing

        # Create a new entry in the database for the file
        new_file_uploaded_id = SequencingFileUploaded.create(
            file_sequencer_id, file_dict
        )

        # If a new filename is provided, copy the file to the new location
        if new_filename:
            # Get the data of the SequencingSequencerId to get the region
            sequencerId = SequencingSequencerId.get(file_sequencer_id)
            region = sequencerId.Region
            bucket = process_data["project_id"]

            processed_folder = f"seq_processed/{uploads_folder}"
            processed_file_path = f"{processed_folder}/{new_filename}"
            os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
            shutil.copy2(final_file_path, processed_file_path)

            # Generate FastQC report
            init_create_fastqc_report(
                new_filename, processed_folder, bucket, region
            )

            # Copy the file to the correct bucket and folder
            init_bucket_chunked_upload_v2(
                local_file_path=processed_file_path,
                destination_upload_directory=region,
                destination_blob_name=new_filename,
                sequencer_file_id=new_file_uploaded_id,
                bucket_name=bucket,
                known_md5=expected_md5,
            )
            return new_filename

    return None  # No matching sequencer ID or no processing occurred


@metadata_bp.route("/metadata_form", endpoint="metadata_form")
@login_required
@approved_required
@admin_or_owner_required
def metadata_form():
    my_buckets = {}
    map_key = os.environ.get("GOOGLE_MAP_API_KEY")
    google_sheets_template_url = os.environ.get("GOOGLE_SPREADSHEET_TEMPLATE")
    for my_bucket in current_user.buckets:
        my_buckets[my_bucket] = Bucket.get(my_bucket)
    expected_columns = get_columns_data(exclude=False)
    project_common_data = get_project_common_data()
    process_data = None
    process_id = request.args.get("process_id", "")
    primer_set_regions = get_primer_sets_regions()
    forward_primers = list(
        {key.split("/")[0]: None for key in primer_set_regions}.keys()
    )
    forward_to_reverse = primers_forward_to_reverse(primer_set_regions)
    samples_data = []
    sequencer_ids = []
    regions = SequencingUpload.get_regions()
    nr_files_per_sequence = 1
    valid_samples = False
    missing_sequencing_ids = []
    samples_data_complete = []
    extra_data = {}
    extra_data_keys = set()
    multiqc_report_exists = False
    mapping_files_exist = False
    has_empty_fastqc_report = False
    lotus2_report = []
    rscripts_report = []
    pdf_report = False
    is_owner = False
    total_uploaded_files = 0

    if process_id:
        process_data = SequencingUpload.get(process_id)
        if process_data is not None:
            is_owner = current_user.id == process_data["user_id"]

            nr_files_per_sequence = process_data["nr_files_per_sequence"]
            regions = process_data["regions"]

            samples_data = SequencingUpload.get_samples(process_id)

            samples_data = sanitize_data(samples_data)

            # lets create the extra data dictionary
            # Iterate through each sample in samples_data
            for sample in samples_data:
                # Ensure that both 'SampleID' and 'extracolumns_json'
                # exist in the sample
                if "SampleID" in sample:
                    extracolumns_json = sample.get("extracolumns_json")

                    if (
                        extracolumns_json
                    ):  # Check if extracolumns_json is not None
                        # Add to extra_data dictionary
                        extra_data[sample["SampleID"]] = extracolumns_json

                        # Update the set of unique keys with keys from the
                        # extracolumns_json dictionary
                        extra_data_keys.update(extracolumns_json.keys())
            # lets delete the extracolumns_json from the samples_data
            for sample in samples_data:
                if "extracolumns_json" in sample:
                    del sample["extracolumns_json"]
            sequencer_ids = SequencingUpload.get_sequencer_ids(process_id)
            valid_samples = SequencingUpload.validate_samples(process_id)
            missing_sequencing_ids = (
                SequencingUpload.check_missing_sequencer_ids(process_id)
            )
            samples_data_complete = (
                SequencingUpload.get_samples_with_sequencers_and_files(
                    process_id
                )
            )

            # check if we have files without fastq report
            has_empty_fastqc_report = any(
                not file.get("fastqc_report")
                for entry in samples_data_complete
                for sequencer in entry.get("sequencer_ids", [])
                for file in sequencer.get("uploaded_files", [])
            )

            total_uploaded_files = sum(
                len(sequencer["uploaded_files"])
                for sample in samples_data_complete
                for sequencer in sample.get("sequencer_ids", [])
            )

            multiqc_report_exists = check_multiqc_report(process_id)
            mapping_files_exist = SequencingUpload.check_mapping_files_exist(
                process_id
            )

            lotus2_report = SequencingUpload.check_lotus2_reports_exist(
                process_id
            )
            rscripts_report = SequencingUpload.check_rscripts_reports_exist(
                process_id
            )
            # check if pdf report exists
            r_scripts_report = os.path.join(
                "seq_processed",
                process_data["uploads_folder"],
                "r_output",
                "report.pdf",
            )
            if os.path.isfile(r_scripts_report):
                pdf_report = True
        else:
            return redirect(url_for("metadata.metadata_form"))

    return render_template(
        "metadata_form.html",
        my_buckets=my_buckets,
        map_key=map_key,
        expected_columns=expected_columns,
        project_common_data=project_common_data,
        process_data=process_data,
        process_id=process_id,
        samples_data=samples_data,
        regions=regions,
        sequencer_ids=sequencer_ids,
        forward_primers=forward_primers,
        forward_to_reverse=forward_to_reverse,
        nr_files_per_sequence=nr_files_per_sequence,
        google_sheets_template_url=google_sheets_template_url,
        valid_samples=valid_samples,
        missing_sequencing_ids=missing_sequencing_ids,
        samples_data_complete=samples_data_complete,
        is_admin=current_user.admin,
        multiqc_report_exists=multiqc_report_exists,
        extra_data_keys=extra_data_keys,
        extra_data=extra_data,
        mapping_files_exist=mapping_files_exist,
        lotus2_report=lotus2_report,
        has_empty_fastqc_report=has_empty_fastqc_report,
        rscripts_report=rscripts_report,
        pdf_report=pdf_report,
        is_owner=is_owner,
        total_uploaded_files=total_uploaded_files,
    )


@metadata_bp.route(
    "/metadata_validate_row",
    methods=["POST"],
    endpoint="metadata_validate_row",
)
@login_required
@approved_required
@admin_or_owner_required
def metadata_validate_row():
    # we have panda available, and because we want to reuse the same
    # existing functions, we want to put all the data from the form
    # into a df
    # Read the data of the form in a df
    process_id = request.form.get("process_id")
    process_data = SequencingUpload.get(process_id)

    # Parse form data from the request
    form_data = request.form.to_dict()

    # Convert form data to a DataFrame
    df = pd.DataFrame([form_data])

    # Check metadata using the helper function
    if "Date_collected" in df.columns:
        # Attempt to convert 'Date_collected' to datetime
        # format, invalid parsing will be NaT
        temp_dates = pd.to_datetime(df["Date_collected"], errors="coerce")

        # Update only the rows where conversion was successful
        mask = temp_dates.notna()
        df.loc[mask, "Date_collected"] = temp_dates[mask].dt.strftime(
            "%Y-%m-%d"
        )
    using_scripps_txt = "no"
    if process_data["using_scripps"] == 1:
        using_scripps_txt = "yes"

    result = check_metadata(df, using_scripps_txt)

    if result["status"] == 1:
        for _, row in df.iterrows():
            # Convert the row to a dictionary
            datadict = row.to_dict()
            SequencingSample.create(
                sequencingUploadId=process_id, datadict=datadict
            )
    # Return the result as JSON
    return (
        jsonify(
            {
                "result": result,
                "data": df.replace({np.nan: None}).to_dict(orient="records"),
            }
        ),
        200,
    )


@metadata_bp.route(
    "/upload_metadata_file", methods=["POST"], endpoint="upload_metadata_file"
)
@login_required
@approved_required
@admin_or_owner_required
def upload_metadata_file():
    file = request.files.get("file")
    using_scripps = request.form.get("using_scripps")
    process_id = request.form.get("process_id")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Read uploaded file and get its column names
    filename = file.filename
    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == ".csv":
        df = pd.read_csv(file, sep=None, engine="python")
        logger.info(df)
    elif file_extension in [".xls", ".xlsx"]:
        df = pd.read_excel(file, engine="openpyxl")
    else:
        return jsonify({"error": "Unsupported file type"}), 400
    df = df.dropna(how="all")
    df = df.apply(
        lambda col: col.str.strip() if col.dtype == "object" else col
    )

    if "Date_collected" in df.columns:
        # Attempt to convert 'Date_collected' to datetime
        # format, invalid parsing will be NaT
        temp_dates = pd.to_datetime(df["Date_collected"], errors="coerce")

        # Update only the rows where conversion was successful
        mask = temp_dates.notna()
        df.loc[mask, "Date_collected"] = temp_dates[mask].dt.strftime(
            "%Y-%m-%d"
        )

    # Strip degree symbols at the end of Latitude and Longitude values
    if "Latitude" in df.columns:
        df["Latitude"] = df["Latitude"].astype(str).str.rstrip("°")
    if "Longitude" in df.columns:
        df["Longitude"] = df["Longitude"].astype(str).str.rstrip("°")

    # Check metadata using the helper function
    result = check_metadata(df, using_scripps)

    expected_columns_data = get_columns_data(exclude=True)
    expected_columns = list(expected_columns_data.keys())
    if result["status"] == 1:

        # if all is good, lets save the file they uploaded.
        process_data = SequencingUpload.get(process_id)
        uploads_folder = process_data["uploads_folder"]

        save_path = f"seq_uploads/{uploads_folder}/" f"samples_file_{filename}"
        file.save(save_path)

        # Create a list to hold the sample line IDs
        sample_line_ids = []
        # All the data that was uploaded was ok. Lets save them
        df = df.replace({np.nan: None})
        # Iterate over rows and create samples
        for _, row in df.iterrows():
            # Convert the row to a dictionary
            datadict = row.to_dict()
            # Call the create method of SequencingSample and
            # capture the sample_line_id
            sample_line_id = SequencingSample.create(
                sequencingUploadId=process_id, datadict=datadict
            )
            # Append the sample_line_id to the list
            sample_line_ids.append(sample_line_id)

        # Update DataFrame with sample_line_id
        df["id"] = sample_line_ids
    else:
        # When status is not 1, leave 'id' column as None or empty
        df["id"] = None
    # Return the result as JSON
    return (
        jsonify(
            {
                "result": result,
                "data": df.replace({np.nan: None}).to_dict(orient="records"),
                "expectedColumns": expected_columns,
            }
        ),
        200,
    )


@metadata_bp.route(
    "/upload_process_common_fields",
    methods=["POST"],
    endpoint="upload_process_common_fields",
)
@login_required
@approved_required
def upload_process_common_fields():
    from helpers.slack import send_message_to_slack

    # Parse form data from the request
    form_data = request.form.to_dict()
    if form_data["process_id"]:
        process_id = form_data["process_id"]
        if current_user.admin:
            from models.db_model import SequencingUploadsTable

            # Get the valid columns of the SequencingUploadsTable
            valid_fields = {
                column.key
                for column in inspect(SequencingUploadsTable).columns
            }
            # Loop through form_data keys and update fields that are valid
            for key, value in form_data.items():
                logger.info(
                    "The key is " + str(key) + " and the value " + str(value)
                )
                if key in valid_fields and key not in [
                    "using_scripps",
                    "project_id",
                ]:
                    SequencingUpload.update_field(
                        id=process_id, fieldname=key, value=value
                    )

    else:
        process_id = SequencingUpload.create(datadict=form_data)
        send_message_to_slack(
            "STARTING: A v2 upload was initiated by filling "
            + "in project common data by the user "
            + current_user.name
            + ". The project is: "
            + str(form_data["project_id"])
            + ". The id of the upload is: "
            + str(process_id)
        )

    # Return the result as JSON
    return (
        jsonify({"result": "ok", "process_id": process_id}),
        200,
    )


@metadata_bp.route(
    "/add_sequencer_id",
    methods=["POST"],
    endpoint="add_sequencer_id",
)
@login_required
@approved_required
def add_sequencer_id():
    # Parse form data from the request
    form_data = request.form.to_dict()
    # Return the result as JSON
    sequencer_id, existing = SequencingSequencerId.create(
        sample_id=form_data["sequencer_sample_id"],
        sequencer_id=form_data["sequencer_id"],
        region=form_data["sequencer_region"],
        index_1=form_data["index_1"],
        index_2=form_data["index_2"],
    )
    missing_sequencing_ids = SequencingUpload.check_missing_sequencer_ids(
        form_data["process_id"]
    )
    return (
        jsonify(
            {
                "result": "ok",
                "sequencer_id": sequencer_id,
                "existing": existing,
                "missing_sequencing_ids": missing_sequencing_ids,
            }
        ),
        200,
    )


@metadata_bp.route(
    "/upload_sequencer_ids_file",
    methods=["POST"],
    endpoint="upload_sequencer_ids_file",
)
@login_required
@approved_required
@admin_or_owner_required
def upload_sequencer_ids_file():
    file = request.files.get("file")
    process_id = request.form.get("process_id")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Read uploaded file and get its column names
    filename = file.filename
    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == ".csv":
        df = pd.read_csv(file)
    elif file_extension in [".xls", ".xlsx"]:
        df = pd.read_excel(file, engine="openpyxl")
    else:
        return jsonify({"error": "Unsupported file type"}), 400
    df = df.dropna(how="all")

    process_data = SequencingUpload.get(process_id)
    result = SequencingSequencerId.check_df_and_add_records(
        process_id=process_id,
        df=df,
        process_data=process_data,
    )
    missing_sequencing_ids = SequencingUpload.check_missing_sequencer_ids(
        process_id
    )
    result["missing_sequencing_ids"] = missing_sequencing_ids

    return (jsonify(result), 200)


@metadata_bp.route(
    "/sequencing_confirm_metadata",
    methods=["POST"],
    endpoint="sequencing_confirm_metadata",
)
@login_required
@approved_required
@admin_or_owner_required
def sequencing_confirm_metadata():
    process_id = request.form.get("process_id")

    SequencingUpload.mark_upload_confirmed_as_true(process_id)

    return (jsonify({"result": 1}), 200)


@metadata_bp.route(
    "/delete_sequencer_ids",
    methods=["GET"],
    endpoint="delete_sequencer_ids",
)
@login_required
@approved_required
@admin_required
def delete_sequencer_ids():
    process_id = request.args.get("process_id")
    SequencingUpload.delete_sequencer_ids_for_upload(process_id)

    return redirect(
        url_for("metadata.metadata_form", process_id=process_id) + "#step_7"
    )


@metadata_bp.route(
    "/sequencing_revert_confirm_metadata",
    methods=["GET"],
    endpoint="sequencing_revert_confirm_metadata",
)
@login_required
@approved_required
@admin_required
def sequencing_revert_confirm_metadata():
    process_id = request.args.get("process_id")
    logger.info("here")
    SequencingUpload.mark_upload_confirmed_as_false(process_id)

    return redirect(
        url_for("metadata.metadata_form", process_id=process_id) + "#step_5"
    )


@metadata_bp.route(
    "/metadata_instructions",
    endpoint="metadata_instructions",
)
def metadata_instructions():
    expected_columns = get_columns_data(exclude=True)
    google_sheets_template_url = os.environ.get("GOOGLE_SPREADSHEET_TEMPLATE")

    return render_template(
        "metadata_instructions.html",
        expected_columns=expected_columns,
        google_sheets_template_url=google_sheets_template_url,
    )


@metadata_bp.route("/xls_sample", endpoint="xls_sample")
def xls_sample():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = Path(project_root, "static", "xls")
    xls_path = path / "template_with_dropdowns_for_one_drive_and_excel.xlsx"

    return send_file(xls_path, as_attachment=True)


@metadata_bp.route(
    "/create_xls_template",
    endpoint="create_xls_template",
)
@login_required
@approved_required
def create_xls_template():
    create_template_one_drive_and_excel()

    return (jsonify({"result": 1}), 200)


@metadata_bp.route(
    "/check_filename_matching",
    methods=["POST"],
    endpoint="check_filename_matching",
)
@login_required
@approved_required
@admin_or_owner_required
def check_filename_matching():
    process_id = request.form.get("process_id")
    filename = request.form.get("filename")

    if not process_id or not filename:
        return (
            jsonify(
                {"result": 2, "message": "Missing process_id or filename"}
            ),
            400,
        )

    matching_sequencer_ids = SequencingSequencerId.get_matching_sequencer_ids(
        process_id, filename
    )

    if len(matching_sequencer_ids) == 1:
        # Extract the sequencer ID
        sequencer_id = matching_sequencer_ids[0]
        sequencer_id_data = SequencingSequencerId.get(sequencer_id)
        # Fetch process data and uploaded files
        process_data = SequencingUpload.get(process_id)
        if not process_data:
            return (
                jsonify({"result": 2, "message": "Process data not found"}),
                404,
            )
        nr_files_per_sequence = process_data.get("nr_files_per_sequence", 0)
        uploaded_files = SequencingUpload.get_uploaded_files(process_id)

        # Filter uploaded files by sequencer_id
        files_for_sequencer = [
            file
            for file in uploaded_files
            if file["sequencerId"] == sequencer_id
        ]

        # Check if we have the correct number of files uploaded
        if len(files_for_sequencer) >= nr_files_per_sequence:
            return (
                jsonify(
                    {
                        "result": 0,
                        "message": "All expected files already uploaded "
                        + "for the sequencerID "
                        + str(sequencer_id_data.SequencerID),
                    }
                ),
                200,
            )

        return (
            jsonify({"result": 1, "matching_sequencer_id": sequencer_id}),
            200,
        )

    if len(matching_sequencer_ids) > 1:
        return (
            jsonify(
                {
                    "result": 1,
                    "message": "File matches more than one sequencer ID",
                }
            ),
            200,
        )

    return (
        jsonify({"result": 1, "message": "No matching sequencer IDs found"}),
        200,
    )


# NOTE: The "POST" method handles
# the upload of the file itself.
# There is also a "GET" method
# that checks if the chunk has
# been uploaded
@metadata_bp.route(
    "/sequencing_upload_chunk",
    methods=["POST"],
    endpoint="sequencing_upload_chunk",
)
@login_required
@approved_required
def sequencing_upload_chunk():
    process_id = request.args.get("process_id")
    file = request.files.get("file")

    if file and process_id:
        process_data = SequencingUpload.get(process_id)
        uploads_folder = process_data["uploads_folder"]

        resumable_chunk_number = request.args.get("resumableChunkNumber")
        chunk_number = (
            int(resumable_chunk_number) if resumable_chunk_number else 1
        )

        save_path = (
            f"seq_uploads/{uploads_folder}/"
            f"{file.filename}.part{chunk_number}"
        )

        # Reset pointer before saving
        file.seek(0)

        # Save file chunk once
        file.save(save_path)

        return jsonify({"message": f"Chunk {chunk_number} uploaded"}), 200

    return jsonify({"message": "No file received or no process_id"}), 400


# NOTE: The "GET" method is only used on the same
# url as the sending of the data in order
# to determine if this chunk has been uploaded
# There is also a "POST" method that handles
# the upload of the file itself.
@metadata_bp.route(
    "/sequencing_upload_chunk",
    methods=["GET"],
    endpoint="sequencing_upload_chunk_check",
)
@login_required
@approved_required
@admin_or_owner_required
def sequencing_upload_chunk_check():
    process_id = request.args.get("process_id")
    chunk_number = request.args.get("resumableChunkNumber")
    resumable_filename = request.args.get("resumableFilename")

    if process_id:
        process_data = SequencingUpload.get(process_id)
        uploads_folder = process_data["uploads_folder"]

        chunk_path = (
            f"seq_uploads/{uploads_folder}/"
            f"{resumable_filename}.part{chunk_number}"
        )

        if os.path.exists(chunk_path):
            logger.info(f"Chunk {chunk_number} exists at {chunk_path}")
            return "", 200  # Chunk already uploaded, return 200
        else:
            logger.warning(
                f"Chunk {chunk_number} does not exist at {chunk_path}"
            )

    return "", 204  # Chunk not found, return 204


# The resumamble library indicates to us
# that all chunks of the file were uploaded
# Check that this is the case
# and if yes, rename it and complete the process
@metadata_bp.route(
    "/sequencing_file_upload_completed",
    methods=["POST"],
    endpoint="sequencing_file_upload_completed",
)
@login_required
@approved_required
@admin_or_owner_required
def sequencing_file_upload_completed():
    process_id = request.form.get("process_id")
    if process_id:
        process_data = SequencingUpload.get(process_id)
        uploads_folder = process_data["uploads_folder"]

        fileopts_json = request.form.get("fileopts")
        fileopts = json.loads(fileopts_json)
        form_filename = fileopts["filename"]
        # form_filesize = fileopts["filesize"]
        form_filechunks = fileopts["filechunks"]
        expected_md5 = fileopts["md5"]

        final_file_path = f"seq_uploads/{uploads_folder}/{form_filename}"
        temp_file_path = f"seq_uploads/{uploads_folder}/{form_filename}.temp"
        # Make sure we dont continue writting on a previous failed effort
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        with open(temp_file_path, "ab") as temp_file:
            for i in range(1, form_filechunks + 1):
                chunk_path = (
                    f"seq_uploads/{uploads_folder}/{form_filename}.part{i}"
                )
                with open(chunk_path, "rb") as chunk_file:
                    temp_file.write(chunk_file.read())

        actual_md5 = calculate_md5(temp_file_path)
        # Compare MD5 hashes
        if expected_md5 == actual_md5:
            # MD5 hashes match, file integrity verified
            os.rename(temp_file_path, final_file_path)
            # Then, since it is now confirmed, lets delete the parts
            for i in range(1, form_filechunks + 1):
                chunk_path = (
                    f"seq_uploads/{uploads_folder}/{form_filename}.part{i}"
                )
                os.remove(chunk_path)

            source_directory = f"seq_uploads/{uploads_folder}"
            new_filename = process_uploaded_file(
                process_id=process_id,
                source_directory=source_directory,
                filename=form_filename,
                expected_md5=expected_md5,
                process_data=process_data,
            )
            if new_filename:
                return (
                    jsonify(
                        {
                            "result": 1,
                            "original_filename": form_filename,
                            "new_name": new_filename,
                        }
                    ),
                    200,
                )

    return "", 200


@metadata_bp.route(
    "/user_uploads_v2", methods=["GET"], endpoint="user_uploads_v2"
)
@login_required
@approved_required
def user_uploads_v2():
    user_id = request.args.get("user_id")
    user = User.get(user_id)
    if (current_user.admin) or (current_user.id == user_id):
        user_metadata_uploads = SequencingUpload.get_all(user_id=user_id)
        return render_template(
            "user_uploads_v2.html",
            user_uploads=user_metadata_uploads,
            user_id=user_id,
            is_admin=current_user.admin,
            username=user.name,
            user_email=user.email,
        )
    else:
        return redirect(url_for("user.only_admins"))


@metadata_bp.route(
    "/all_uploads_v2", methods=["GET"], endpoint="all_uploads_v2"
)
@login_required
@admin_required
@approved_required
def all_uploads_v2():
    user_metadata_uploads = SequencingUpload.get_all()
    return render_template(
        "user_uploads_v2.html",
        user_uploads=user_metadata_uploads,
        user_id="",
        is_admin=current_user.admin,
        username="",
        user_email="",
    )


@metadata_bp.route(
    "/delete_upload_process_v2",
    methods=["GET"],
    endpoint="delete_upload_process_v2",
)
@admin_required
@login_required
@approved_required
def delete_upload_process_v2():
    process_id = request.args.get("process_id")
    return_to = request.args.get("return_to")
    process_data = SequencingUpload.get(process_id)
    uploads_folder = process_data["user_id"]
    if uploads_folder:
        delete_bucket_folder("uploads/" + uploads_folder)
    SequencingUpload.delete_upload_and_files(process_id)
    if return_to == "user":
        user_id = request.args.get("user_id")
        return redirect(url_for("metadata.user_uploads_v2", user_id=user_id))
    else:
        return redirect(url_for("metadata.all_uploads_v2"))


@metadata_bp.route(
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


@metadata_bp.route(
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


@metadata_bp.route(
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
        url_for("metadata.metadata_form", process_id=process_id) + "#step_10"
    )


@metadata_bp.route(
    "/confirm_files_uploading_finished",
    methods=["POST"],
    endpoint="confirm_files_uploading_finished",
)
@login_required
@approved_required
@admin_or_owner_required
def confirm_files_uploading_finished():
    process_id = request.form.get("process_id")
    SequencingUpload.update_field(
        process_id, "files_uploading_confirmed", True
    )
    return redirect(
        url_for("metadata.metadata_form", process_id=process_id) + "#step_9"
    )


@metadata_bp.route(
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


@metadata_bp.route(
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
        url_for("metadata.metadata_form", process_id=process_id) + "#step_14"
    )


@metadata_bp.route(
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


@metadata_bp.route(
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


@metadata_bp.route(
    "/ensure_bucket_uploads",
    methods=["GET"],
    endpoint="ensure_bucket_uploads",
)
@login_required
@admin_required
@approved_required
def ensure_bucket_uploads():
    process_id = request.args.get("process_id")
    if process_id:
        SequencingUpload.ensure_bucket_upload_progress(process_id)
    return {}


@metadata_bp.route(
    "/check_bucket_uploads",
    methods=["GET"],
    endpoint="check_bucket_uploads",
)
@login_required
@admin_required
@approved_required
def check_bucket_uploads():
    process_id = request.args.get("process_id")
    if process_id:
        result = SequencingUpload.check_all_files_uploaded(process_id)
        return (
            jsonify({"result": result}),
            200,
        )
    return {}


@metadata_bp.route(
    "/delete_local_project_files",
    methods=["GET"],
    endpoint="delete_local_project_files",
)
@login_required
@admin_required
@approved_required
def delete_local_project_files():
    process_id = request.args.get("process_id")
    if process_id:
        result = SequencingUpload.delete_local_files(process_id)
        return (
            jsonify({"result": result}),
            200,
        )
    return {}


@metadata_bp.route(
    "/download_process_files_from_bucket",
    methods=["GET"],
    endpoint="download_process_files_from_bucket",
)
@login_required
@admin_required
@approved_required
def download_process_files_from_bucket():
    process_id = request.args.get("process_id")
    if process_id:
        result = SequencingUpload.download_files_from_bucket(process_id)
        return (
            jsonify({"result": result}),
            200,
        )
    return {}


@metadata_bp.route(
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


@metadata_bp.route(
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


@metadata_bp.route(
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
        url_for("metadata.metadata_form", process_id=process_id) + "#step_11"
    )


@metadata_bp.route(
    "/sequencing_process_server_file",
    methods=["POST"],
    endpoint="sequencing_process_server_file",
)
@login_required
@approved_required
@admin_required
def sequencing_process_server_file():
    process_id = request.form.get("process_id")
    directory_name = request.form.get("directory_name")
    sequencing_run = request.form.get("sequencing_run")

    if process_id:
        process_data = SequencingUpload.get(process_id)

        # Construct the full directory path
        full_directory_path = Path(directory_name)

        # Check if the directory exists
        if not full_directory_path.is_dir():
            logger.error(f"Directory not found: {full_directory_path}")
            return {"error": "Directory not found"}, 404

        # Initialize the report list and a counter for processed files
        report = []
        processed_files_count = 0
        max_files_to_process = 150

        # Loop through files in the directory
        for file_path in full_directory_path.iterdir():
            # Stop processing if we've reached the limit
            if processed_files_count >= max_files_to_process:
                logger.info(
                    f"Maximum of {max_files_to_process} files processed."
                )
                break

            # Check if the file ends with '.fastq.gz'
            if file_path.is_file() and (
                file_path.name.endswith(".fastq.gz")
                or file_path.name.endswith(".fq.gz")
            ):

                actual_md5 = calculate_md5(file_path)

                # Process and rename the file
                new_filename = process_uploaded_file(
                    process_id=process_id,
                    source_directory=directory_name,
                    filename=file_path.name,
                    expected_md5=actual_md5,
                    process_data=process_data,
                    sequencing_run=sequencing_run,
                )

                # Only increment the counter if file was successfully processed
                if new_filename:
                    report.append(
                        {
                            "original_filename": file_path.name,
                            "new_filename": new_filename,
                        }
                    )
                    processed_files_count += 1

        # Return the report as part of the response
        return {
            "message": (
                f"Files processed successfully. "
                f"Processed {processed_files_count} files."
            ),
            "report": report,
        }, 200

    return {"message": "No process_id provided"}, 400


@metadata_bp.route(
    "/generate_lotus2_report",
    methods=["POST"],
    endpoint="generate_lotus2_report",
)
@login_required
@approved_required
@admin_required
def generate_lotus2_report():
    process_id = request.form.get("process_id")
    debug = request.form.get("debug")
    analysis_type_id = request.form.get("analysis_type_id")
    process_data = SequencingUpload.get(process_id)
    region = request.form.get("region")

    sdmopt = request.form.get("sdmopt")
    parameters = {}
    if sdmopt in [
        "sdm_miSeq_ITS",
        "sdm_miSeq_ITS_200",
        "sdm_miSeq_ITS_forward",
        "sdm_miSeq2_SSU_Spun",
        "sdm_miSeq2_250",
    ]:
        parameters["sdmopt"] = sdmopt
    input_dir = "seq_processed/" + process_data["uploads_folder"]
    init_generate_lotus2_report(
        process_id, input_dir, region, debug, analysis_type_id, parameters
    )

    return jsonify({"result": 1})


@metadata_bp.route(
    "/delete_lotus2_report",
    methods=["POST"],
    endpoint="delete_lotus2_report",
)
@login_required
@approved_required
@admin_required
def delete_lotus2_report():
    process_id = request.form.get("process_id")
    analysis_type_id = request.form.get("analysis_type_id")
    process_data = SequencingUpload.get(process_id)

    input_dir = "seq_processed/" + process_data["uploads_folder"]
    delete_generated_lotus2_report(process_id, input_dir, analysis_type_id)

    return jsonify({"result": 1})


@metadata_bp.route(
    "/generate_rscripts_report",
    methods=["POST"],
    endpoint="generate_rscripts_report",
)
@login_required
@approved_required
@admin_required
def generate_rscripts_report():
    process_id = request.form.get("process_id")
    analysis_type_id = request.form.get("analysis_type_id")
    process_data = SequencingUpload.get(process_id)
    region = request.form.get("region")

    input_dir = "seq_processed/" + process_data["uploads_folder"]
    init_generate_rscripts_report(
        process_id, input_dir, region, analysis_type_id
    )

    return jsonify({"result": 1})


@metadata_bp.route(
    "/delete_rscripts_report",
    methods=["POST"],
    endpoint="delete_rscripts_report",
)
@login_required
@approved_required
@admin_required
def delete_rscripts_report():
    process_id = request.form.get("process_id")
    region = request.form.get("region")
    analysis_type_id = request.form.get("analysis_type_id")

    process_data = SequencingUpload.get(process_id)

    input_dir = "seq_processed/" + process_data["uploads_folder"]
    delete_generated_rscripts_report(
        process_id, input_dir, region, analysis_type_id
    )
    return jsonify({"result": 1})


@metadata_bp.route(
    "/delete_all_region_rscripts_reports",
    methods=["GET"],
    endpoint="delete_all_region_rscripts_reports",
)
@login_required
@approved_required
@admin_required
def delete_all_region_rscripts_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    # process_id = request.form.get("process_id")
    region = request.args.get("region")
    analysis_type_id = request.args.get("analysis_type_id")
    anti_nuke = request.args.get("anti_nuke")

    if (
        anti_nuke_env is not None
        and anti_nuke_env != ""
        and anti_nuke_env == anti_nuke
    ):
        if region is not None and analysis_type_id is not None:

            processes_data = SequencingUpload.get_all()

            for process_data in processes_data:
                for region_type, analysis_list in process_data[
                    "analysis"
                ].items():
                    for analysis in analysis_list:
                        if (
                            analysis["analysis_id"] is not None
                            and str(analysis_type_id)
                            == str(analysis["analysis_type_id"])
                            and analysis["rscripts_status"] == "Finished"
                        ):
                            input_dir = (
                                "seq_processed/"
                                + process_data["uploads_folder"]
                            )
                            delete_generated_rscripts_report(
                                process_data["id"],
                                input_dir,
                                region,
                                analysis_type_id,
                            )
    else:
        return jsonify({"result": "Not passing antinuke"})
    return jsonify({"result": 1})


@metadata_bp.route(
    "/generate_all_region_rscripts_reports",
    methods=["GET"],
    endpoint="generate_all_region_rscripts_reports",
)
@login_required
@approved_required
@admin_required
def generate_all_region_rscripts_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    # process_id = request.form.get("process_id")
    region = request.args.get("region")
    analysis_type_id = request.args.get("analysis_type_id")
    anti_nuke = request.args.get("anti_nuke")

    if (
        anti_nuke_env is not None
        and anti_nuke_env != ""
        and anti_nuke_env == anti_nuke
    ):
        if region is not None and analysis_type_id is not None:
            from helpers.r_scripts import init_generate_all_rscripts_reports

            init_generate_all_rscripts_reports(region, analysis_type_id)
    else:
        return jsonify({"result": "Not passing antinuke"})
    return jsonify({"result": 1})


@metadata_bp.route(
    "/show_report_outcome", methods=["GET"], endpoint="show_report_outcome"
)
@login_required
@approved_required
@admin_or_owner_required
def show_report_outcome():
    process_id = request.args.get("process_id")
    analysis_type_id = request.args.get("analysis_type_id")
    file_type = request.args.get("type")  # Renamed 'file' to 'type'
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if file_type in [
        "LotuS_progout",
        "demulti",
        "LotuS_run",
        "lotus2_command_outcome",
        "phyloseq",
        "rscripts_command_outcome",
        "LibrarySize",
        "control_vs_sample",
        "filtered_rarefaction",
        "physeq_decontam",
        "metadata_chaorichness",
        "physeq_by_genus",
        "contaminants",
    ]:
        # Fetch process data from SequencingUpload model
        process_data = SequencingUpload.get(process_id)

        uploads_folder = process_data["uploads_folder"]

        if file_type in [
            "LotuS_progout",
            "demulti",
            "LotuS_run",
            "lotus2_command_outcome",
            "phyloseq",
        ]:
            # Check the lotus2 report details
            lotus2_report = SequencingUpload.check_lotus2_reports_exist(
                process_id
            )

            # Find the corresponding region in the lotus2 report
            lotus2_region_data = next(
                (
                    item
                    for item in lotus2_report
                    if str(item["analysis_type_id"]) == str(analysis_type_id)
                ),
                None,
            )

            if lotus2_region_data:
                log_folder = os.path.join(
                    "seq_processed",
                    uploads_folder,
                    "lotus2_report",
                    lotus2_region_data["analysis_type"],
                    "LotuSLogS",
                )
                # Handle log files and command_output
                if file_type == "LotuS_progout":
                    file_path = os.path.join(log_folder, "LotuS_progout.log")
                elif file_type == "demulti":
                    file_path = os.path.join(log_folder, "demulti.log")
                elif file_type == "LotuS_run":
                    file_path = os.path.join(log_folder, "LotuS_run.log")
                elif file_type == "phyloseq":
                    report_folder = Path(
                        project_root,
                        "seq_processed",
                        uploads_folder,
                        "lotus2_report",
                        lotus2_region_data["analysis_type"],
                    )
                    file_path = os.path.join(report_folder, "phyloseq.Rdata")
                    return send_file(file_path, as_attachment=True)
                elif file_type == "lotus2_command_outcome":
                    logger.info("here we are")
                    command_output = lotus2_region_data[
                        "lotus2_command_outcome"
                    ]
                    if command_output:
                        return (
                            command_output,
                            200,
                            {"Content-Type": "text/plain"},
                        )
                    else:
                        return {"error": "Command output not found"}, 404

            # Check if the file exists
            if os.path.isfile(file_path):
                # Open and return the contents of the file
                with open(file_path, "r") as f:
                    file_contents = f.read()
                return file_contents, 200, {"Content-Type": "text/plain"}
            else:
                return {"error": "File not found"}, 404

        if file_type in [
            "rscripts_command_outcome",
            "LibrarySize",
            "control_vs_sample",
            "filtered_rarefaction",
            "physeq_decontam",
            "metadata_chaorichness",
            "physeq_by_genus",
            "contaminants",
        ]:

            # Check the rscripts report details
            rscripts_report = SequencingUpload.check_rscripts_reports_exist(
                process_id
            )
            # Find the corresponding region in the lotus2 report
            rscipts_region_data = next(
                (
                    item
                    for item in rscripts_report
                    if str(item["analysis_type_id"]) == str(analysis_type_id)
                ),
                None,
            )

            if rscipts_region_data:
                # Construct the base path for the log folder

                report_folder = Path(
                    project_root,
                    "seq_processed",
                    uploads_folder,
                    "r_output",
                    rscipts_region_data["analysis_type"],
                )
                # Handle log files and command_output
                if file_type == "LibrarySize":
                    file_path = os.path.join(report_folder, "LibrarySize.pdf")
                    return send_file(file_path)
                elif file_type == "control_vs_sample":
                    file_path = os.path.join(
                        report_folder, "control_vs_sample.pdf"
                    )
                    return send_file(file_path)
                elif file_type == "contaminants":
                    file_path = os.path.join(report_folder, "contaminants.csv")
                    return send_file(file_path)
                elif file_type == "filtered_rarefaction":
                    file_path = os.path.join(
                        report_folder, "filtered_rarefaction.pdf"
                    )
                    return send_file(file_path)
                elif file_type == "physeq_decontam":
                    file_path = os.path.join(
                        report_folder, "physeq_decontam.Rdata"
                    )
                    return send_file(file_path, as_attachment=True)
                elif file_type == "metadata_chaorichness":
                    file_path = os.path.join(
                        report_folder, "metadata_chaorichness.csv"
                    )
                    return send_file(file_path, as_attachment=True)
                elif file_type == "physeq_by_genus":
                    file_path = os.path.join(
                        report_folder, "ecm_physeq_by_genus.pdf"
                    )
                    if rscipts_region_data["analysis_type"] in [
                        "SSU_dada2",
                        "SSU_vsearch",
                        "SSU_eukaryome",
                    ]:
                        file_path = os.path.join(
                            report_folder, "amf_physeq_by_genus.pdf"
                        )
                    return send_file(file_path, as_attachment=True)

                elif file_type == "rscripts_command_outcome":
                    # fix this !!!
                    command_output = rscipts_region_data[
                        "rscripts_command_outcome"
                    ]

                    if command_output:
                        return (
                            command_output,
                            200,
                            {"Content-Type": "text/plain"},
                        )
                    else:
                        return {"error": "Command output not found"}, 404

    return {"error": "Invalid request"}, 400


@metadata_bp.route(
    "/upload_report_to_bucket",
    methods=["GET"],
    endpoint="upload_report_to_bucket",
)
@login_required
@approved_required
@admin_required
def upload_report_to_bucket():
    process_id = request.args.get("process_id")
    analysis_type_id = request.args.get("analysis_type_id")
    report = request.args.get("report")
    process_data = SequencingUpload.get(process_id)
    bucket = process_data["project_id"]

    if report in ["lotus2", "rscripts"]:
        from models.sequencing_analysis_type import SequencingAnalysisType

        analysis_type = SequencingAnalysisType.get(analysis_type_id)
        bucket_directory = "report/" + analysis_type.name
        if report == "lotus2":
            output_path = (
                "seq_processed/"
                + process_data["uploads_folder"]
                + "/lotus2_report/"
                + analysis_type.name
            )
            bucket_directory = f"lotus2_report/" f"{analysis_type.name}"
        elif report == "rscripts":
            output_path = (
                "seq_processed/"
                + process_data["uploads_folder"]
                + "/r_output/"
                + analysis_type.name
            )
            bucket_directory = (
                f"lotus2_report/" f"{analysis_type.name}/r_scripts_output"
            )
        from helpers.bucket import init_bucket_upload_folder_v2

        init_bucket_upload_folder_v2(
            folder_path=output_path,
            destination_upload_directory=bucket_directory,
            bucket=bucket,
        )
    return redirect(
        url_for("metadata.metadata_form", process_id=process_id) + "#step_9"
    )


@metadata_bp.route(
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


@metadata_bp.route(
    "/update_missing_geo_data",
    methods=["GET"],
    endpoint="update_missing_geo_data",
)
@login_required
@admin_required
@approved_required
def update_missing_geo_data():

    SequencingSample.update_missing_fields()
    # land_use = get_land_use(-122.4194, 37.7749)
    # resolve_ecoregion = get_resolve_ecoregion(-122.4194, 37.7749)
    # baileys_ecoregion = get_baileys_ecoregion(-122.4194, 37.7749)
    # elevation = get_elevation(-122.4194, 37.7749)
    return jsonify({"done": 1}), 200


@metadata_bp.route(
    "/upload_sequencer_ids_migration_file",
    methods=["POST"],
    endpoint="upload_sequencer_ids_migration_file",
)
@login_required
@admin_required
@approved_required
def upload_sequencer_ids_migration_file():
    file = request.files.get("file")
    process_id = request.form.get("process_id")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Read uploaded file and get its column names
    filename = file.filename
    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == ".csv":
        df = pd.read_csv(file)
    else:
        return jsonify({"error": "Unsupported file type"}), 400
    df = df.dropna(how="all")

    # Retrieve process samples and sequencer IDs
    samples_data_complete = (
        SequencingUpload.get_samples_with_sequencers_and_files(process_id)
    )

    result = []

    # Iterate over each row in the DataFrame
    for _, row in df.iterrows():
        sample_id = row["sample_id"]
        sequencer_id = row["sequencer_id"]

        # Find the sample data for the current sample_id
        sample_data = next(
            (s for s in samples_data_complete if s["SampleID"] == sample_id),
            None,
        )
        if not sample_data:
            result.append(f"No sample found for sample_id: {sample_id}")
            continue

        # Check if the sequencer ID exists for this sample
        existing_sequencer = next(
            (
                s
                for s in sample_data["sequencer_ids"]
                if s["SequencerID"] == sequencer_id
            ),
            None,
        )

        if not existing_sequencer:
            # Create a new sequencer ID record since it doesn't exist
            sequencer_data, existing = SequencingSequencerId.create(
                sample_id=sample_data["id"],
                sequencer_id=sequencer_id,
                region=row["folder"],
                index_1="",
                index_2="",
            )
            result.append(
                f"Created new sequencer ID "
                f"{sequencer_id} for sample {sample_id}."
            )
            # Store the database ID of the newly created sequencer.
            sequencer_db_id = sequencer_data
        else:
            sequencer_db_id = existing_sequencer[
                "id"
            ]  # Use the database ID of the existing sequencer.
            result.append(
                f"Existing sequencer ID {sequencer_id} "
                f"found for sample {sample_id}."
            )

        # Handle the associated files
        existing_files = [
            file
            for sequencer in sample_data["sequencer_ids"]
            if sequencer["id"] == sequencer_db_id
            for file in sequencer.get("uploaded_files", [])
        ]

        # Check if a file with the same original
        # and new filename already exists
        file_exists = any(
            file["original_filename"] == row["old_filename"]
            and file["new_name"] == row["new_filename"]
            for file in existing_files
        )

        if not file_exists:
            # Create a new file record in the database
            file_dict = {
                "original_filename": row["old_filename"],
                "new_name": row["new_filename"],
                "bucket_upload_progress": "100",
            }
            SequencingFileUploaded.create(sequencer_db_id, file_dict)
            result.append(
                f"Created new file record with original filename "
                f"'{row['old_filename']}' and new filename "
                f"'{row['new_filename']}' for sample "
                f"'{sample_id}' and sequencer ID "
                f"'{sequencer_id}'."
            )
        else:
            result.append(
                f"File with original filename '{row['old_filename']}' "
                f"already exists "
                f"for sample '{sample_id}' "
                f"and sequencer ID '{sequencer_id}'."
            )

    return jsonify({"result": 1, "messages": result}), 200


@metadata_bp.route(
    "/export_sample_locations",
    methods=["GET"],
    endpoint="export_sample_locations",
)
@login_required
@admin_required
@approved_required
def export_sample_locations():
    process_id = request.args.get("process_id")

    if process_id:
        SequencingUpload.export_sample_locations(process_id)
        return redirect(
            url_for("metadata.metadata_form", process_id=process_id)
            + "#step_9"
        )


@metadata_bp.route(
    "/reset_primers_count",
    methods=["GET"],
    endpoint="reset_primers_count",
)
@login_required
@admin_required
@approved_required
def reset_primers_count():
    process_id = request.args.get("process_id")

    if process_id:
        SequencingUpload.reset_primers_count(process_id)
        return redirect(
            url_for("metadata.metadata_form", process_id=process_id)
            + "#step_9"
        )


@metadata_bp.route(
    "/adapters_count",
    methods=["GET"],
    endpoint="adapters_count",
)
@login_required
@admin_required
@approved_required
def adapters_count():
    process_id = request.args.get("process_id")

    if process_id:
        SequencingUpload.adapters_count(process_id)
        return "done"


@metadata_bp.route(
    "/adapters_count_all",
    methods=["GET"],
    endpoint="adapters_count_all",
)
@login_required
@admin_required
@approved_required
def adapters_count_all():
    SequencingUpload.adapters_count_all()


@metadata_bp.route(
    "/export_all_richness_data",
    methods=["GET"],
    endpoint="export_all_richness_data",
)
@login_required
@admin_required
@approved_required
def export_all_richness_data():

    export_path = "richness_exports"
    os.makedirs(export_path, exist_ok=True)
    SequencingAnalysis.export_richness_data(
        1, export_path + "/richness_SSU_dada2.csv"
    )
    SequencingAnalysis.export_richness_data(
        2, export_path + "/richness_SSU_vsearch.csv"
    )
    SequencingAnalysis.export_richness_data(
        3, export_path + "/richness_ITS2.csv"
    )
    SequencingAnalysis.export_richness_data(
        4, export_path + "/richness_ITS1.csv"
    )
    return jsonify({"done": 1}), 200


@metadata_bp.route(
    "/generate_all_lotus2_reports",
    methods=["GET"],
    endpoint="generate_all_lotus2_reports",
)
@login_required
@approved_required
@admin_required
def generate_all_lotus2_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    # process_id = request.form.get("process_id")
    analysis_type_id = request.args.get("analysis_type_id")
    anti_nuke = request.args.get("anti_nuke")
    from_id = request.args.get("from_id", default=None)
    to_id = request.args.get("to_id", default=None)
    # Convert to integers only if the parameters are provided
    if from_id is not None:
        try:
            from_id = int(from_id)
        except ValueError:
            raise ValueError(
                "Invalid 'from_id' parameter. Must be an integer."
            )

    if to_id is not None:
        try:
            to_id = int(to_id)
        except ValueError:
            raise ValueError("Invalid 'to_id' parameter. Must be an integer.")

    if (
        anti_nuke_env is not None
        and anti_nuke_env != ""
        and anti_nuke_env == anti_nuke
    ):
        if analysis_type_id is not None:
            init_generate_all_lotus2_reports(analysis_type_id, from_id, to_id)
        else:
            return jsonify({"result": "Something wrong with your input"})
    else:
        return jsonify({"result": "Not passing antinuke"})

    return jsonify({"done": 1}), 200


@metadata_bp.route(
    "/delete_all_lotus2_reports",
    methods=["GET"],
    endpoint="delete_all_lotus2_reports",
)
@login_required
@approved_required
@admin_required
def delete_all_lotus2_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    analysis_type_id = request.args.get("analysis_type_id")
    anti_nuke = request.args.get("anti_nuke")
    from_id = request.args.get("from_id", default=None)
    to_id = request.args.get("to_id", default=None)
    # Convert to integers only if the parameters are provided
    if from_id is not None:
        try:
            from_id = int(from_id)
        except ValueError:
            raise ValueError(
                "Invalid 'from_id' parameter. Must be an integer."
            )

    if to_id is not None:
        try:
            to_id = int(to_id)
        except ValueError:
            raise ValueError("Invalid 'to_id' parameter. Must be an integer.")

    if (
        anti_nuke_env is not None
        and anti_nuke_env != ""
        and anti_nuke_env == anti_nuke
        and analysis_type_id is not None
    ):
        processes_data = SequencingUpload.get_all()

        for process_data in processes_data:

            process_id = process_data["id"]
            # Check if the process_id satisfies the given conditions
            from_id = int(from_id)
            to_id = int(to_id)
            if (
                (from_id is None and to_id is None)
                or (
                    from_id is not None
                    and to_id is None
                    and process_id >= from_id
                )
                or (
                    from_id is None
                    and to_id is not None
                    and process_id <= to_id
                )
                or (
                    from_id is not None
                    and to_id is not None
                    and from_id <= process_id <= to_id
                )
            ):
                logger.info("The process id is " + str(process_id))

                for region_type, analysis_list in process_data[
                    "analysis"
                ].items():
                    for analysis in analysis_list:
                        logger.info(
                            "The analysis id is "
                            + str(analysis["analysis_id"])
                        )
                        logger.info(
                            "The analysis type id is "
                            + str(analysis["analysis_type_id"])
                        )
                        if (
                            analysis["analysis_id"] is not None
                            and analysis["lotus2_status"] == "Finished"
                            and str(analysis_type_id)
                            == str(analysis["analysis_type_id"])
                        ):
                            logger.info("And we will delete it")
                            input_dir = (
                                "seq_processed/"
                                + process_data["uploads_folder"]
                            )
                            delete_generated_lotus2_report(
                                process_data["id"], input_dir, analysis_type_id
                            )
    else:
        return jsonify({"result": "Not passing antinuke"})
    return jsonify({"result": 1})


@metadata_bp.route(
    "/get_sequencers_sample", methods=["GET"], endpoint="get_sequencers_sample"
)
@login_required
@approved_required
def get_sequencers_sample():
    process_data = None
    process_id = request.args.get("process_id", "")
    if process_id:
        process_data = SequencingUpload.get(process_id)
        # logger.info(process_data)
        if process_data is not None:
            samples_data = SequencingUpload.get_samples(process_id)
            # logger.info(samples_data)

    # Define CSV headers
    fieldnames = ["SampleID", "Region", "SequencerID", "Index_1", "Index_2"]

    # Create CSV data
    csv_data = []
    for sample in samples_data:
        for region in process_data["regions"]:
            csv_data.append(
                {
                    "SampleID": sample["SampleID"],
                    "Region": region,
                    "SequencerID": "",  # Empty field
                    "Index_1": "",  # Empty field
                    "Index_2": "",  # Empty field
                }
            )

    # Generate CSV response
    def generate():
        yield ",".join(fieldnames) + "\n"  # Header row
        for row in csv_data:
            yield ",".join([str(row[field]) for field in fieldnames]) + "\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sequencer_ids.csv"
        },
    )


@metadata_bp.route(
    "/download_metadata",
    methods=["GET"],
    endpoint="download_metadata",
)
@login_required
@approved_required
@admin_or_owner_required
def download_metadata():
    process_id = request.args.get("process_id")
    process_data = SequencingUpload.get(process_id)

    if process_data is None:
        return "Process data not found", 404

    samples_data = SequencingUpload.get_samples(process_id)

    # Define CSV headers (Sample columns first, Process columns last)
    sample_columns = [
        "SampleID",
        "Site_name",
        "Latitude",
        "Longitude",
        "Vegetation",
        "Land_use",
        "Agricultural_land",
        "Ecosystem",
        "ResolveEcoregion",
        "BaileysEcoregion",
        "Grid_Size",
        "Soil_depth",
        "Transport_refrigeration",
        "Drying",
        "Date_collected",
        "DNA_concentration_ng_ul",
        "Elevation",
        "Sample_type",
        "Sample_or_Control",
        "IndigenousPartnership",
        "Notes",
    ]

    process_columns = [
        "Country",
        "Expedition_lead",
        "Collaborators",
    ]

    fieldnames = (
        sample_columns + process_columns
    )  # Order: Sample first, Process last

    def safe_get(data_dict, key):
        # Ensures missing keys or None values are
        # # replaced with an empty string."""
        return str(data_dict.get(key, "") or "")

    def generate():
        # Use csv.writer to handle quoting
        import io

        output = io.StringIO()
        writer = csv.writer(
            output, quoting=csv.QUOTE_MINIMAL
        )  # Ensures proper quoting

        # Write header row
        writer.writerow(fieldnames)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for sample in samples_data:
            row = [safe_get(sample, col) for col in sample_columns] + [
                safe_get(process_data, col) for col in process_columns
            ]

            writer.writerow(row)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"metadata_{process_data.get('project_id', 'unknown')}.csv"
    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@metadata_bp.route(
    "/edit_sample",
    methods=["GET"],
    endpoint="edit_sample",
)
@login_required
@approved_required
@admin_or_owner_required
def edit_sample():
    process_id = request.args.get("process_id")
    sample_id = request.args.get("sample_id")

    # Retreive the data for the sample
    expected_columns = get_columns_data(exclude=False)
    sample = SequencingSample.get(sample_id)

    # Check that sample_id is part of this process_id
    if int(sample.sequencingUploadId) != int(process_id):
        logger.info(sample.sequencingUploadId)
        return jsonify({"result": "Incorrect sample or process_id"})

    logger.info(process_id)
    logger.info(sample)

    return render_template(
        "metadata_edit_sample.html",
        expected_columns=expected_columns,
        sample=sample,
    )


@metadata_bp.route(
    "/update_sample",
    methods=["POST"],
    endpoint="update_sample",
)
@login_required
@approved_required
@admin_or_owner_required
def update_sample():
    process_id = request.form.get("process_id")
    sample_id = request.form.get("sample_id")

    sample = SequencingSample.get(sample_id)

    if not sample:
        return jsonify({"result": "Sample not found"}), 404

    if int(sample.sequencingUploadId) != int(process_id):
        return jsonify({"result": "Incorrect sample or process_id"}), 400

    # Collect the data from the form
    datadict = request.form.to_dict()

    # Update the sample
    if SequencingSample.update(sample_id, datadict):
        return jsonify({"success": True}), 200
    else:
        return jsonify({"result": "Failed to update sample"}), 500


@metadata_bp.route(
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
        url_for("metadata.metadata_form", process_id=process_id) + "#step_14"
    )


@metadata_bp.route(
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
        url_for("metadata.metadata_form", process_id=process_id) + "#step_14"
    )


@metadata_bp.route("/primers_chart", endpoint="primers_chart")
@login_required
@approved_required
@admin_or_owner_required
def primers_chart():
    process_id = request.args.get("process_id", "")
    region = request.args.get("region", "ITS2")  # default to ITS2
    project_id = ""
    chart_data = []

    if process_id:
        process_data = SequencingUpload.get(process_id)
        if process_data is not None:
            project_id = process_data["project_id"]
            samples_data_complete = (
                SequencingUpload.get_samples_with_sequencers_and_files(
                    process_id
                )
            )

            for sample in samples_data_complete:
                sample_id = sample["SampleID"]
                for sequencer in sample["sequencer_ids"]:
                    if sequencer["Region"] != region:
                        continue

                    files = sequencer.get("uploaded_files", [])
                    if not files or not files[0].get("total_sequences_number"):
                        continue

                    total = files[0]["total_sequences_number"]
                    if total == 0:
                        continue

                    chart_data.append(
                        {
                            "sample_id": sample_id,
                            "fwd_read_fwd_adap": round(
                                100
                                * (sequencer.get("fwd_read_fwd_adap") or 0)
                                / total,
                                2,
                            ),
                            "rev_read_rev_adap": round(
                                100
                                * (sequencer.get("rev_read_rev_adap") or 0)
                                / total,
                                2,
                            ),
                            "fwd_rev_adap": round(
                                100
                                * (sequencer.get("fwd_rev_adap") or 0)
                                / total,
                                2,
                            ),
                            "fwd_rev_mrg_adap": round(
                                100
                                * (sequencer.get("fwd_rev_mrg_adap") or 0)
                                / total,
                                2,
                            ),
                        }
                    )

    return render_template(
        "primers_chart.html",
        chart_data=chart_data,
        region=region,
        project_id=project_id,
        process_id=process_id,
    )
