import docker
import logging
import shutil
from datetime import datetime

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def init_generate_lotus2_report(region_nr, process_id, input_dir, region):

    from tasks import generate_lotus2_report_async

    try:
        result = generate_lotus2_report_async.delay(
            region_nr, process_id, input_dir, region
        )
        logger.info(
            f"Celery generate_lotus2_report_async task "
            f"called successfully! Task ID: {result.id}"
        )
        from models.sequencing_upload import SequencingUpload

        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_lotus2_report_task_id",
            result.id,
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_lotus2_report_started_at",
            datetime.utcnow(),
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_lotus2_report_status",
            "Started",
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


def generate_lotus2_report(region_nr, process_id, input_dir, region):
    client = docker.from_env()
    from models.sequencing_upload import SequencingUpload

    logger.info("Trying for:")
    logger.info(" - region_nr : " + str(region_nr))
    logger.info(" - process_id : " + str(process_id))
    logger.info(" - input_dir : " + str(input_dir))
    logger.info(" - region : " + str(region))

    try:
        # Run Lotus2 inside the 'spun-lotus2' container
        container = client.containers.get("spun-lotus2")
        output_path = input_dir + "/lotus2_report/" + region

        if region == "ITS2":

            refDB = (
                "/lotus2_files/UNITE/sh_refs_qiime_ver10_97_04.04.2024.fasta"
            )
            tax4refDB = (
                "/lotus2_files/UNITE/sh_taxonomy_qiime_ver10_97_04.04.2024.txt"
            )
            sdmopt = "/lotus2_files/sdm_miSeq_ITS.txt"
            mapping_file = input_dir + "/mapping_files/ITS2_Mapping.txt"

            logger.info(" - Here we will try the command")
            command = [
                "lotus2",
                "-i",
                input_dir,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                refDB,
                "-tax4refDB",
                tax4refDB,
                "-amplicon_type",
                region,
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
                sdmopt,
                "-id",
                "0.97",
            ]
            logger.info(" - the command is: ")
            logger.info(command)
            # Run the command inside the container
            result = container.exec_run(command)
            logger.info(result.output)

            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_lotus2_report_status",
                "Finished",
            )
            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_lotus2_report_result",
                result.output,
            )

        elif region == "SSU":

            # SILVA ONLY
            # The following two would be if we only
            # wanted to use the SILVA database
            refDB = (
                "lotus2_files/SILVA/SILVA_138.2_SSURef_NR99_tax_silva.fasta.gz"
            )
            tax4refDB = "lotus2_files/SILVA/SLV_138.1_SSU.tax"

            # The following two is if we want to use
            # both the ___ and the SILVA database
            refDB = (
                "lotus2_files/vt_types_fasta_from_05-06-2019.qiime.fasta,"
                "lotus2_files/SILVA/SLV_138.1_SSU.fasta"
            )

            tax4refDB = (
                "/lotus2_files/vt_types_GF.txt,"
                "lotus2_files/SILVA/SLV_138.1_SSU.tax"
            )

            sdmopt = "/usr/local/share/lotus2-2.34.1-0/configs/sdm_miSeq2.txt"
            mapping_file = input_dir + "/mapping_files/SSU_Mapping.txt"

            logger.info(" - Here we will try the command")
            command = [
                "lotus2",
                "-i",
                input_dir,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                refDB,
                "-tax4refDB",
                tax4refDB,
                "-amplicon_type",
                region,
                "-LCA_idthresh",
                "97,95,93,91,88,78,0",
                "-tax_group",
                "fungi",
                "-taxAligner",
                "blast",
                "-clustering",
                "dada2",
                "-LCA_cover",
                "0.97",
                "-derepMin",
                "10:1,5:2,3:3",
                "-sdmopt",
                sdmopt,
            ]
            logger.info(" - the command is: ")
            logger.info(command)
            # Run the command inside the container
            result = container.exec_run(command)
            logger.info(result.output)

            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_lotus2_report_status",
                "Finished",
            )
            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_lotus2_report_result",
                result.output,
            )

        else:
            logger.info(
                "Lotus2 report generation for amplicon "
                + region
                + " cannot be generated as we don't have the details."
            )
            SequencingUpload.update_field(
                process_id,
                "region_" + str(region_nr) + "_lotus2_report_status",
                "Abandoned. Unknown region.",
            )

    except Exception as e:
        logger.error(f"Error generating Lotus2 report: {str(e)}")
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_lotus2_report_status",
            "Error while generating.",
        )
        SequencingUpload.update_field(
            process_id,
            "region_" + str(region_nr) + "_lotus2_report_result",
            str(e),
        )


def delete_generated_lotus2_report(region_nr, process_id, input_dir, region):

    from models.sequencing_upload import SequencingUpload

    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_lotus2_report_task_id",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_lotus2_report_started_at",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_lotus2_report_status",
        None,
    )
    SequencingUpload.update_field(
        process_id,
        "region_" + str(region_nr) + "_lotus2_report_result",
        None,
    )
    output_path = input_dir + "/lotus2_report/" + region
    shutil.rmtree(output_path)

    return {"msg": "Process initiated"}
