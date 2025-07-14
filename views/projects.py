import logging
import os
from flask_login import login_required, current_user
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
)
from models.sequencing_upload import SequencingUpload
from models.sequencing_analysis import SequencingAnalysis
from models.user import User
from helpers.lotus2 import (
    delete_generated_lotus2_report,
    init_generate_all_lotus2_reports,
)
from helpers.decorators import (
    approved_required,
    admin_required,
)
from helpers.bucket import (
    delete_bucket_folder,
)
from helpers.r_scripts import (
    delete_generated_rscripts_report,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

projects_bp = Blueprint("projects", __name__)


@projects_bp.route(
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


@projects_bp.route(
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
        return redirect(url_for("projects.user_uploads_v2", user_id=user_id))
    else:
        return redirect(url_for("projects.all_uploads_v2"))


@projects_bp.route(
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


@projects_bp.route(
    "/delete_all_lotus2_reports",
    methods=["POST"],
    endpoint="delete_all_lotus2_reports",
)
@login_required
@approved_required
@admin_required
def delete_all_lotus2_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    analysis_type_id = request.form.get("analysis_type_id")
    anti_nuke = request.form.get("anti_nuke")
    from_id = request.form.get("from_id", default=None)
    to_id = request.form.get("to_id", default=None)
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


@projects_bp.route(
    "/generate_all_lotus2_reports",
    methods=["POST"],
    endpoint="generate_all_lotus2_reports",
)
@login_required
@approved_required
@admin_required
def generate_all_lotus2_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    analysis_type_id = request.args.get("analysis_type_id")
    anti_nuke = request.form.get("anti_nuke")
    from_id = request.form.get("from_id", default=None)
    to_id = request.form.get("to_id", default=None)
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


@projects_bp.route(
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


@projects_bp.route(
    "/adapters_count_all",
    methods=["GET"],
    endpoint="adapters_count_all",
)
@login_required
@admin_required
@approved_required
def adapters_count_all():
    SequencingUpload.adapters_count_all()


@projects_bp.route(
    "/generate_all_region_rscripts_reports",
    methods=["POST"],
    endpoint="generate_all_region_rscripts_reports",
)
@login_required
@approved_required
@admin_required
def generate_all_region_rscripts_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    region = request.form.get("region")
    analysis_type_id = request.form.get("analysis_type_id")
    anti_nuke = request.form.get("anti_nuke")

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


@projects_bp.route(
    "/delete_all_region_rscripts_reports",
    methods=["POST"],
    endpoint="delete_all_region_rscripts_reports",
)
@login_required
@approved_required
@admin_required
def delete_all_region_rscripts_reports():
    anti_nuke_env = os.environ.get("ANTI_NUKE_STRING")
    region = request.form.get("region")
    analysis_type_id = request.form.get("analysis_type_id")
    anti_nuke = request.form.get("anti_nuke")

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


@projects_bp.route(
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


@projects_bp.route(
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


@projects_bp.route(
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


@projects_bp.route(
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
