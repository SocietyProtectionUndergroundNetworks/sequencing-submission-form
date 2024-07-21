import logging
import pandas as pd
import os
from flask import (
    redirect,
    Blueprint,
    render_template,
    request,
    url_for,
    jsonify,
)
from flask_login import current_user, login_required
from models.bucket import Bucket
from models.sequencing_upload import SequencingUpload
from models.sequencing_sample import SequencingSample
from models.sequencing_sequencer_ids import SequencingSequencerId
from helpers.metadata_check import (
    check_metadata,
    get_columns_data,
    get_project_common_data,
    get_regions,
    get_nr_files_per_sequence,
)
from helpers.model import model_to_dict
from helpers.create_xls_template import (
    create_template_with_options_sheet,
    create_template_google_sheets
)
import numpy as np


metadata_bp = Blueprint("metadata", __name__)

logger = logging.getLogger("my_app_logger")


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


@metadata_bp.route("/metadata_form", endpoint="metadata_form")
@login_required
@approved_required
def metadata_form():
    my_buckets = {}
    map_key = os.environ.get("GOOGLE_MAP_API_KEY")
    for my_bucket in current_user.buckets:
        my_buckets[my_bucket] = Bucket.get(my_bucket)
    expected_columns = get_columns_data()
    project_common_data = get_project_common_data()
    process_data = None
    process_id = request.args.get("process_id", "")
    samples_data = []
    sequencer_ids = []
    regions = get_regions()
    nr_files_per_sequence = 1
    if process_id:
        process_data = SequencingUpload.get(process_id)
        nr_files_per_sequence = get_nr_files_per_sequence(
            process_data.Sequencing_platform
        )

        process_data = model_to_dict(process_data)  # Convert to dictionary
        samples_data = SequencingUpload.get_samples(process_id)
        sequencer_ids = SequencingUpload.get_sequencer_ids(process_id)
        regions = get_regions(process_data)

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
        nr_files_per_sequence=nr_files_per_sequence,
    )


@metadata_bp.route(
    "/metadata_validate_row",
    methods=["POST"],
    endpoint="metadata_validate_row",
)
@login_required
@approved_required
def metadata_validate_row():
    # we have panda available, and because we want to reuse the same
    # existing functions, we want to put all the data from the form
    # into a df
    # Read the data of the form in a df

    # Parse form data from the request
    form_data = request.form.to_dict()

    # Convert form data to a DataFrame
    df = pd.DataFrame([form_data])
    logger.info("\n%s", df.to_string())
    # Check metadata using the helper function
    result = check_metadata(df, "yes")

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
def upload_metadata_file():
    file = request.files.get("file")
    using_scripps = request.form.get("using_scripps")
    process_id = request.form.get("process_id")
    multiple_sequencing_runs = request.form.get("Multiple_sequencing_runs")
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
    # Check metadata using the helper function
    result = check_metadata(df, using_scripps, multiple_sequencing_runs)

    expected_columns_data = get_columns_data()
    expected_columns = list(expected_columns_data.keys())
    logger.info(result)
    if result["status"] == 1:
        logger.info("the process id is")
        logger.info(process_id)
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
    # Parse form data from the request
    form_data = request.form.to_dict()
    logger.info(form_data)

    # if they have selected Scripps on step 2, we update the
    # relevant values
    if ("using_scripps" in form_data) and (
        form_data["using_scripps"] == "yes"
    ):
        logger.info(form_data["using_scripps"])

    process_id = SequencingUpload.create(datadict=form_data)

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
    )
    return (
        jsonify(
            {
                "result": "ok",
                "sequencer_id": sequencer_id,
                "existing": existing,
            }
        ),
        200,
    )


@metadata_bp.route(
    "/upload_sequencing_file",
    methods=["POST"],
    endpoint="upload_sequencing_file",
)
@login_required
@approved_required
def upload_sequencing_file():
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
    process_data = model_to_dict(process_data)
    result = SequencingSequencerId.check_df_and_add_records(
        process_id=process_id,
        df=df,
        process_data=process_data,
    )

    return (jsonify(result), 200)


@metadata_bp.route(
    "/sequencing_confirm_metadata",
    methods=["POST"],
    endpoint="sequencing_confirm_metadata",
)
@login_required
@approved_required
def sequencing_confirm_metadata():
    process_id = request.form.get("process_id")

    SequencingUpload.mark_upload_confirmed_as_true(process_id)

    return (jsonify({"result": 1}), 200)


@metadata_bp.route(
    "/create_xls_template",
    endpoint="create_xls_template",
)
@login_required
@approved_required
def create_xls_template():
    # create_template()
    # create_template_one_drive()
    create_template_with_options_sheet()
    create_template_google_sheets()

    return (jsonify({"result": 1}), 200)
