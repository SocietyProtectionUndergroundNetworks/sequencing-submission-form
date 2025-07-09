from . import upload_form_bp
import os
import logging
import shutil
import json
from pathlib import Path
from flask_login import login_required
from flask import (
    redirect,
    request,
    url_for,
    jsonify,
)
from helpers.decorators import (
    approved_required,
    admin_required,
    admin_or_owner_required,
)
from helpers.bucket import (
    init_bucket_chunked_upload_v2,
    calculate_md5,
)
from helpers.fastqc import (
    init_create_fastqc_report,
)
from models.sequencing_upload import SequencingUpload
from models.sequencing_files_uploaded import SequencingFileUploaded
from models.sequencing_sequencer_ids import SequencingSequencerId

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


@upload_form_bp.route(
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
        url_for("upload_form_bp.metadata_form", process_id=process_id)
        + "#step_9"
    )


@upload_form_bp.route(
    "/sequencing_process_server_files",
    methods=["POST"],
    endpoint="sequencing_process_server_files",
)
@login_required
@approved_required
@admin_required
def sequencing_process_server_files():
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


# The js library "resumamble" indicates to us
# that all chunks of the file were uploaded
# Check that this is the case
# and if yes, rename it and complete the process
@upload_form_bp.route(
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


# NOTE: The "GET" method is only used on the same
# url as the sending of the data in order
# to determine if this chunk has been uploaded
# There is also a "POST" method that handles
# the upload of the file itself.
@upload_form_bp.route(
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


# NOTE: The "POST" method handles
# the upload of the file itself.
# There is also a "GET" method
# that checks if the chunk has
# been uploaded
@upload_form_bp.route(
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


@upload_form_bp.route(
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
