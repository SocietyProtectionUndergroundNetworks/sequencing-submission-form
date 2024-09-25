import docker
import logging
from datetime import datetime

# PROCESS_DIR =
client = docker.from_env()
logger = logging.getLogger("my_app_logger")


def init_generate_lotus2_report(process_id, input_dir, amplicon_type):

    from tasks import generate_lotus2_report_async

    try:
        result = generate_lotus2_report_async.delay(
            process_id, input_dir, amplicon_type
        )
        logger.info(
            f"Celery generate_lotus2_report_async task "
            f"called successfully! Task ID: {result.id}"
        )
        from models.sequencing_upload import SequencingUpload

        SequencingUpload.update_field(
            process_id, "lotus2_report_task_id", result.id
        )
        SequencingUpload.update_field(
            process_id, "lotus2_report_started_at", datetime.utcnow()
        )
        SequencingUpload.update_field(
            process_id, "lotus2_report_status", "Started"
        )

    except Exception as e:
        logger.error(
            "This is an error message from helpers/bucket.py "
            " while trying to generate_lotus2_report_async"
        )
        logger.error(e)
        return {
            "error": (
                "This is an error message from helpers/bucket.py "
                " while trying to generate_lotus2_report_async"
            ),
            "e": (e),
        }

    return {"msg": "Process initiated"}


def generate_lotus2_report(process_id, input_dir, amplicon_type):

    try:
        # Run Lotus2 inside the 'spun-lotus2' container
        container = client.containers.get("spun-lotus2")
        command = [
            "lotus2",
            "-i",
            input_dir,
            "-o",
            input_dir + "/lotus2_report",
            "-m",
            input_dir + "/mapping_files/ITS2_Mapping.txt",
            "-refDB",
            "/lotus2_files/UNITE/sh_refs_qiime_ver10_97_04.04.2024.fasta",
            "-tax4refDB",
            "/lotus2_files/UNITE/sh_taxonomy_qiime_ver10_97_04.04.2024.txt",
            "-amplicon_type",
            amplicon_type,
            "-LCA_idthresh",
            "97,95,93,91,88,78",
            "-tax_group",
            "fungi",
            "-taxAligner",
            "blast",
            "-clustering",
            "vsearch",
            "-derepMin",
            "10:1,5:2,3:3",
            "-sdmopt",
            "/lotus2_files/sdm_miSeq_ITS.txt",
            "-id",
            "0.97",
        ]

        # Run the command inside the container
        result = container.exec_run(command)
        logger.info(result.output)

        from models.sequencing_upload import SequencingUpload

        SequencingUpload.update_field(
            process_id, "lotus2_report_status", "Finished"
        )
        SequencingUpload.update_field(
            process_id, "lotus2_report_result", result.output
        )

        # Log the status of report generation
        logger.info("Lotus2 report generation has finished.")

    except Exception as e:
        logger.error(f"Error generating Lotus2 report: {str(e)}")
