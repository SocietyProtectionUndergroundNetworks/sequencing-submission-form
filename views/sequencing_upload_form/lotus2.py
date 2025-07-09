# Includes routes for lotus2 and rscripts analysing and showing the data
from . import upload_form_bp
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
)
from helpers.lotus2 import (
    init_generate_lotus2_report,
    delete_generated_lotus2_report,
)
from models.sequencing_upload import SequencingUpload


@upload_form_bp.route(
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


@upload_form_bp.route(
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


@upload_form_bp.route(
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
        url_for("upload_form_bp.metadata_form", process_id=process_id) + "#step_9"
    )
