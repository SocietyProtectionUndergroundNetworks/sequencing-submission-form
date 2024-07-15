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
from helpers.metadata_check import (
    check_metadata,
    get_columns_data,
    get_project_common_data,
)
from helpers.model import model_to_dict
import numpy as np


metadata_bp = Blueprint("metadata", __name__)

logger = logging.getLogger("my_app_logger")

logger.info("Test here 4 1")


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
    if process_id:
        process_data = SequencingUpload.get(process_id)
        logger.info(process_data)
        process_data = model_to_dict(process_data)  # Convert to dictionary
    
    return render_template(
        "metadata_form.html",
        my_buckets=my_buckets,
        map_key=map_key,
        expected_columns=expected_columns,
        project_common_data=project_common_data,
        process_data=process_data,
        process_id=process_id
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

    # Check metadata using the helper function
    result = check_metadata(df, using_scripps, multiple_sequencing_runs)

    expected_columns_data = get_columns_data()
    expected_columns = list(expected_columns_data.keys())

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
        logger.info('we are switching the Sequencing_facility to Scripps')
        logger.info(form_data["using_scripps"])
        form_data["Sequencing_facility"] = "Scripps"

    process_id = SequencingUpload.create(
        datadict=form_data
    )

    # Return the result as JSON
    return (
        jsonify(
            {
                "result": "ok",
                "process_id": process_id
            }
        ),
        200,
    )
