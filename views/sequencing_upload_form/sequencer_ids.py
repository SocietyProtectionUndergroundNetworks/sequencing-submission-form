from . import upload_form_bp
import os
import pandas as pd
import logging
from flask_login import login_required
from flask import (
    request,
    jsonify,
    Response,
    redirect,
    url_for,
    render_template,
)
from helpers.decorators import (
    approved_required,
    admin_required,
    admin_or_owner_required,
)
from models.sequencing_upload import SequencingUpload
from models.sequencing_files_uploaded import SequencingFileUploaded
from models.sequencing_sequencer_ids import SequencingSequencerId

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_7"
    )


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route("/primers_chart", endpoint="primers_chart")
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
