from . import upload_form_bp
import logging
import os
from pathlib import Path
from flask_login import login_required
from flask import (
    request,
    send_file,
    jsonify,
)
from helpers.decorators import (
    approved_required,
    admin_required,
    staff_or_owner_required,
)
from helpers.r_scripts import (
    init_generate_rscripts_report,
    delete_generated_rscripts_report,
)
from models.sequencing_upload import SequencingUpload

logger = logging.getLogger("my_app_logger")


@upload_form_bp.route(
    "/show_report_outcome", methods=["GET"], endpoint="show_report_outcome"
)
@login_required
@approved_required
@staff_or_owner_required
def show_report_outcome():
    process_id = request.args.get("process_id")
    meta_id = request.args.get("meta_project_id")
    is_meta = bool(meta_id)
    target_id = meta_id if is_meta else process_id
    analysis_type_id = request.args.get("analysis_type_id")
    file_type = request.args.get("type")

    if is_meta:
        from models.meta_project import MetaProject

        process_data = MetaProject.get(target_id)
        # For Meta Projects, result folder is in 'results_folder'
        uploads_folder = process_data.get("results_folder")
        lotus2_report = MetaProject.check_lotus2_reports_exist(target_id)

    else:
        from models.sequencing_upload import SequencingUpload

        process_data = SequencingUpload.get(target_id)
        # For Standard Projects, result folder is in 'uploads_folder'
        uploads_folder = process_data.get("uploads_folder")
        lotus2_report = SequencingUpload.check_lotus2_reports_exist(target_id)

    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    logger.info(
        "Showing report outcome for target_id: %s, is_meta: %s, analysis_type_id: %s, file_type: %s, project_root: %s",
        target_id,
        is_meta,
        analysis_type_id,
        file_type,
        project_root,
    )
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

        if file_type in [
            "LotuS_progout",
            "demulti",
            "LotuS_run",
            "lotus2_command_outcome",
            "phyloseq",
        ]:

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

            if is_meta:
                rscripts_report = MetaProject.check_rscripts_reports_exist(
                    target_id
                )

            else:
                rscripts_report = (
                    SequencingUpload.check_rscripts_reports_exist(target_id)
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


@upload_form_bp.route(
    "/generate_rscripts_report",
    methods=["POST"],
    endpoint="generate_rscripts_report",
)
@login_required
@approved_required
@admin_required
def generate_rscripts_report():
    process_id = request.form.get("process_id")
    meta_id = request.form.get("meta_project_id")
    analysis_type_id = request.form.get("analysis_type_id")
    region = request.form.get("region")

    is_meta = bool(meta_id)
    target_id = meta_id if is_meta else process_id

    if is_meta:
        from models.meta_project import MetaProject

        meta_data = MetaProject.get(target_id)
        input_dir = "seq_processed/" + meta_data["results_folder"]
    else:
        process_data = SequencingUpload.get(target_id)
        input_dir = "seq_processed/" + process_data["uploads_folder"]

    init_generate_rscripts_report(
        target_id, input_dir, region, analysis_type_id, is_meta=is_meta
    )

    return jsonify({"result": 1})


@upload_form_bp.route("/delete_rscripts_report", methods=["POST"])
@login_required
@approved_required
@admin_required
def delete_rscripts_report():
    process_id = request.form.get("process_id")
    meta_id = request.form.get("meta_project_id")  # New
    region = request.form.get("region")
    analysis_type_id = request.form.get("analysis_type_id")

    is_meta = bool(meta_id)
    target_id = meta_id if is_meta else process_id

    if is_meta:
        from models.meta_project import MetaProject

        meta_data = MetaProject.get(target_id)
        input_dir = "seq_processed/" + meta_data["results_folder"]
    else:
        process_data = SequencingUpload.get(target_id)
        input_dir = "seq_processed/" + process_data["uploads_folder"]

    delete_generated_rscripts_report(
        target_id, input_dir, region, analysis_type_id, is_meta=is_meta
    )
    return jsonify({"result": 1})
