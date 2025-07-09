from . import upload_form_bp
import os
import logging
import csv
import pandas as pd
import numpy as np
from flask_login import login_required
from flask import (
    request,
    jsonify,
    render_template,
    Response,
    url_for,
    redirect,
)
from helpers.decorators import (
    approved_required,
    admin_or_owner_required,
    admin_required,
)
from helpers.metadata_check import (
    check_metadata,
    get_columns_data,
)
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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


# Note: Currently there is no url anywhere in the app leading to this endpoint
# It can only be called directly from the browser.
@upload_form_bp.route(
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
            url_for("upload_form_bp.metadata_form", process_id=process_id)
            + "#step_9"
        )


@upload_form_bp.route(
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


@upload_form_bp.route(
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
        url_for("upload_form_bp.metadata_form", process_id=process_id)
        + "#step_5"
    )
