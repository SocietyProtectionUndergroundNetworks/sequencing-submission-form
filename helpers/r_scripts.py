import docker
import logging
import shutil
import os
from datetime import datetime

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def init_generate_rscripts_report(
    region_nr, process_id, input_dir, region, debug=False, clustering=""
):

    from tasks import generate_rscripts_report_async

    try:
        result = generate_rscripts_report_async.delay(
            region_nr, process_id, input_dir, region, debug
        )
        logger.info(
            f"Celery generate_rscripts_report_async task "
            f"called successfully! Task ID: {result.id}"
        )
        from models.sequencing_upload import SequencingUpload

        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_rscripts_report_task_id",
            result.id,
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_rscripts_report_started_at",
            datetime.utcnow(),
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_rscripts_report_status",
            "Started",
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


def generate_rscripts_report(region_nr, process_id, input_dir, region, debug):
    client = docker.from_env()
    from models.sequencing_upload import SequencingUpload

    logger.info("Trying for:")
    logger.info(" - region_nr : " + str(region_nr))
    logger.info(" - process_id : " + str(process_id))
    logger.info(" - input_dir : " + str(input_dir))
    logger.info(" - region : " + str(region))
    logger.info(" - debug : " + str(debug))

    debug_command = ""
    if debug == 1:
        debug_command = " -v --debug "
        logger.info(debug_command)

    try:
        # Run rscripts inside the 'spun-r_service' container
        lotus_2_dir = "/" + input_dir + "/lotus2_report/" + region
        output_dir = "/" + input_dir + "/" + region + "_r_output"
        container = client.containers.get("spun-r-service")

        if region in ["ITS1", "ITS2"]:
            r_script = "EcM_decontam_taxonomic_filtering.R"

        if region in ["SSU"]:
            r_script = "AMF_decontam_taxonomic_filtering.R"

        if region in ["ITS1", "ITS2", "SSU"]:
            os.makedirs(input_dir + "/" + region + "_r_output", exist_ok=True)

            command = ["Rscript", r_script, lotus_2_dir, output_dir]
            command_str = " ".join(command)
            logger.info(" - Here we will try the command")
            logger.info(command_str)
            # Run the command inside the container
            result = container.exec_run(["bash", "-c", command_str])
            logger.info(result.output)

            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_rscripts_report_status",
                "Finished",
            )
            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_rscripts_report_result",
                result.output,
            )

        else:
            logger.info(
                "R scripts generation for amplicon "
                + region
                + " cannot be generated as it is not "
                + " one of the regions we have programmed "
            )
            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_rscripts_report_status",
                "Abandoned. Unknown region.",
            )

    except Exception as e:
        logger.error(f"Error running r scripts: {str(e)}")
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_rscripts_report_status",
            "Error while generating.",
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_rscripts_report_result",
            str(e),
        )


def delete_generated_rscripts_report(region_nr, process_id, input_dir, region):

    from models.sequencing_upload import SequencingUpload

    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_rscripts_report_task_id",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_rscripts_report_started_at",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_rscripts_report_status",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_rscripts_report_result",
        None,
    )
    output_path = input_dir + "/" + region + "_r_output"
    if os.path.exists(output_path):
        shutil.rmtree(output_path)

    return {"msg": "Process initiated"}
