import docker
import logging
import shutil
import os
from datetime import datetime

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


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
    from models.sequencing_analysis import SequencingAnalysis
    from models.sequencing_analysis_type import SequencingAnalysisType

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

            command = ["Rscript", r_script, lotus_2_dir, output_dir]
            command_str = " ".join(command)
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

            output_path = input_dir + "/r_output/" + analysis_type.name
            if os.path.exists(output_path):
                shutil.rmtree(output_path)

    return {"msg": "Process initiated"}
