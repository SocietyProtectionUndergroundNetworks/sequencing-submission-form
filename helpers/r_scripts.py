import docker
import logging
import shutil
import os
import json
import shlex
from datetime import datetime

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def create_pdf_report(process_id):
    from models.sequencing_upload import SequencingUpload

    # check if we have ITS2, ITS1, SSU_DADA analysis ready.
    process_data = SequencingUpload.get(process_id)
    uploads_folder = process_data["uploads_folder"]

    rscripts_reports = SequencingUpload.check_rscripts_reports_exist(
        process_id
    )
    # lets find out if we have an ITS
    its_report = None
    ssu_report = None
    for r_report in rscripts_reports:
        logger.info(r_report["analysis_type"])
        if "ITS2" == r_report["analysis_type"]:
            its_report = r_report["analysis_type"]
        elif "SSU_dada2" == r_report["analysis_type"]:
            ssu_report = r_report["analysis_type"]

    # constract the r command
    command = [
        "Rscript",
        "generate_pdf_report.R",
        "-p",
        "/seq_processed/" + str(uploads_folder),
    ]
    if its_report:
        command.extend(["-i", str(its_report)])

    if ssu_report:
        command.extend(["-s", str(ssu_report)])

    command_str = " ".join(shlex.quote(arg) for arg in command)
    logger.info(command_str)
    # run it
    client = docker.from_env()
    container = client.containers.get("spun-r-service")
    # Run the command inside the container
    result = container.exec_run(["bash", "-c", command_str])
    logger.info(result.output)


def init_generate_rscripts_report(
    process_id,
    input_dir,
    region,
    analysis_type_id="0",
):

    from tasks import generate_rscripts_report_async
    from models.sequencing_analysis import SequencingAnalysis

    if analysis_type_id != 0:
        analysis_id = SequencingAnalysis.get_by_upload_and_type(
            process_id, analysis_type_id
        )
        if analysis_id:
            try:
                result = generate_rscripts_report_async.delay(
                    process_id, input_dir, region, analysis_type_id
                )
                logger.info(
                    f"Celery generate_rscripts_report_async task "
                    f"called successfully! Task ID: {result.id}"
                )

                SequencingAnalysis.update_field(
                    analysis_id, "rscripts_celery_task_id", result.id
                )
                SequencingAnalysis.update_field(
                    analysis_id, "rscripts_started_at", datetime.utcnow()
                )
                SequencingAnalysis.update_field(
                    analysis_id, "rscripts_status", "Started"
                )

            except Exception as e:
                logger.error(
                    "This is an error message from helpers/bucket.py "
                    " while trying to generate_rscripts_report_async"
                )
                logger.error(e)
                return {
                    "error": (
                        "This is an error message from helpers/bucket.py "
                        " while trying to generate_rscripts_report_async"
                    ),
                    "e": (e),
                }

            return {"msg": "Process initiated"}
        else:
            return {"error": "No relevant analysis found"}
    else:
        return {"error": "Wrong analysis type ID"}


def generate_rscripts_report(process_id, input_dir, region, analysis_type_id):
    client = docker.from_env()
    from models.sequencing_upload import SequencingUpload
    from models.sequencing_analysis import SequencingAnalysis
    from models.sequencing_analysis_type import SequencingAnalysisType

    process_data = SequencingUpload.get(process_id)
    project_id = process_data["project_id"]

    # Load the excluded_otus JSON file
    with open("metadataconfig/excluded_otus.json", "r") as f:
        excluded_otus = json.load(f)

    # Filter relevant exclusions
    filtered_exclusions = [
        {"Taxonomy_level": entry["Taxonomy_level"], "Value": entry["Value"]}
        for entry in excluded_otus
        if entry["project_id"] == project_id
    ]

    # Convert to JSON string (ensure it's properly escaped for shell use)
    exclude_json = json.dumps(filtered_exclusions)

    analysis_id = SequencingAnalysis.get_by_upload_and_type(
        process_id, analysis_type_id
    )

    analysis_type = SequencingAnalysisType.get(analysis_type_id)

    lotus_2_dir = "/" + input_dir + "/lotus2_report/" + analysis_type.name
    output_dir = "/" + input_dir + "/r_output/" + analysis_type.name

    logger.info("Trying for:")
    logger.info(" - analysis_type_id : " + str(analysis_type_id))
    logger.info(" - process_id : " + str(process_id))
    logger.info(" - input_dir : " + str(input_dir))
    logger.info(" - region : " + str(region))
    logger.info(" - exclude : " + str(exclude_json))

    try:
        # Run rscripts inside the 'spun-r_service' container
        container = client.containers.get("spun-r-service")

        if region in ["ITS1", "ITS2"]:
            r_script = "EcM_decontam_taxonomic_filtering.R"

        if region in ["SSU"]:
            r_script = "AMF_decontam_taxonomic_filtering.R"

        if region in ["ITS1", "ITS2", "SSU"]:
            os.makedirs(
                input_dir + "/r_output/" + analysis_type.name, exist_ok=True
            )

            # Construct the Rscript command
            command = [
                "Rscript",
                r_script,
                "-l",
                lotus_2_dir,
                "-o",
                output_dir,
            ]

            # Only add -exclude parameter if there are exclusions
            if filtered_exclusions:
                exclude_json = json.dumps(filtered_exclusions)
                command.extend(["--exclude", exclude_json])

            # Escape the command for safe execution
            command_str = " ".join(shlex.quote(arg) for arg in command)
            logger.info(" - Here we will try the command")
            logger.info(command_str)
            # Run the command inside the container
            result = container.exec_run(["bash", "-c", command_str])
            logger.info(result.output)

            SequencingAnalysis.update_field(
                analysis_id, "rscripts_status", "Finished"
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_result", result.output
            )
            SequencingAnalysis.import_richness(analysis_id)

            logger.info("And now we should import the OTUs")
            otu_full_data = (
                input_dir
                + "/r_output/"
                + analysis_type.name
                + "/otu_full_data.csv"
            )
            SequencingUpload.process_otu_data(
                otu_full_data, process_id, analysis_id
            )

        else:
            logger.info(
                "R scripts generation for amplicon "
                + region
                + " cannot be generated as it is not "
                + " one of the regions we have programmed "
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_status", "Abandoned. Unknown region."
            )

    except Exception as e:
        logger.error(f"Error running r scripts: {str(e)}")

        SequencingAnalysis.update_field(
            analysis_id, "rscripts_status", "Error while generating."
        )
        SequencingAnalysis.update_field(analysis_id, "rscripts_result", str(e))


def delete_generated_rscripts_report(
    process_id, input_dir, region, analysis_type_id
):

    if analysis_type_id != 0:
        from models.sequencing_analysis import SequencingAnalysis
        from models.sequencing_analysis_type import SequencingAnalysisType

        analysis_type = SequencingAnalysisType.get(analysis_type_id)

        analysis_id = SequencingAnalysis.get_by_upload_and_type(
            process_id, analysis_type_id
        )

        if analysis_id:
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_celery_task_id", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_started_at", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_finished_at", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_status", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "rscripts_result", None
            )
            SequencingAnalysis.delete_richness_data(analysis_id)
            SequencingAnalysis.delete_otu_data(analysis_id)

            output_path = input_dir + "/r_output/" + analysis_type.name
            if os.path.exists(output_path):
                shutil.rmtree(output_path)

    return {"msg": "Process initiated"}


def init_generate_all_rscripts_reports(region, analysis_type_id):
    from tasks import generate_all_rscripts_reports_async

    generate_all_rscripts_reports_async.delay(region, analysis_type_id)


def generate_all_rscripts_reports(region, analysis_type_id):
    from models.sequencing_upload import SequencingUpload

    processes_data = SequencingUpload.get_all()

    for process_data in processes_data:
        for region_type, analysis_list in process_data["analysis"].items():
            for analysis in analysis_list:
                if (
                    analysis["analysis_id"] is not None
                    and str(analysis_type_id)
                    == str(analysis["analysis_type_id"])
                    and analysis["rscripts_status"] is None
                    and analysis["lotus2_status"] == "Finished"
                ):
                    input_dir = (
                        "seq_processed/" + process_data["uploads_folder"]
                    )
                    logger.info(input_dir)
                    generate_rscripts_report(
                        process_data["id"], input_dir, region, analysis_type_id
                    )
