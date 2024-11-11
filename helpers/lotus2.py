import docker
import logging
import shutil
import os

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def init_generate_lotus2_report(
    region_nr, process_id, input_dir, region, debug=False, clustering=""
):

    from tasks import generate_lotus2_report_async

    from models.sequencing_analysis import SequencingAnalysis

    analysis_id = 0
    # TEMP . If region = SSU, then the typeID =1
    # If the region = ITS2 then the typeID = 3
    # If the region = ITS1 then the typeID = 4
    sequencing_analysis_type = get_analysis_type(region)

    if sequencing_analysis_type != 0:
        analysis_id = SequencingAnalysis.create(
            process_id, sequencing_analysis_type
        )

    try:
        result = generate_lotus2_report_async.delay(
            region_nr, process_id, input_dir, region, debug, clustering
        )
        logger.info(
            f"Celery generate_lotus2_report_async task "
            f"called successfully! Task ID: {result.id}"
        )

        if analysis_id != 0:
            SequencingAnalysis.update_field(
                analysis_id, "celery_task_id", result.id
            )
            SequencingAnalysis.update_field(analysis_id, "status", "Started")

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


def generate_lotus2_report(
    region_nr, process_id, input_dir, region, debug, clustering
):
    client = docker.from_env()
    from models.sequencing_analysis import SequencingAnalysis

    # TEMP . If region = SSU, then the typeID =1
    # If the region = ITS2 then the typeID = 3
    # If the region = ITS1 then the typeID = 4
    sequencing_analysis_type = get_analysis_type(region)

    analysis_id = SequencingAnalysis.get_by_upload_and_type(
        process_id, sequencing_analysis_type
    )

    logger.info("Trying for:")
    logger.info(" - region_nr : " + str(region_nr))
    logger.info(" - process_id : " + str(process_id))
    logger.info(" - input_dir : " + str(input_dir))
    logger.info(" - region : " + str(region))
    logger.info(" - debug : " + str(debug))

    debug_command = ""
    if debug == 1:
        debug_command = " -v --debug "

    try:
        # Run Lotus2 inside the 'spun-lotus2' container
        input_dir = "/" + input_dir
        output_path = input_dir + "/lotus2_report/" + region

        if region in ["ITS1", "ITS2"]:
            container = client.containers.get("spun-lotus2")
            sdmopt = "/lotus2_files/sdm_miSeq_ITS.txt"
            mapping_file = (
                input_dir + "/mapping_files/" + region + "_Mapping.txt"
            )

            logger.info(" - Here we will try the command")
            command = [
                "lotus2",
                debug_command,
                "-i",
                input_dir,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                "UNITE",
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
            command_str = "source activate lotus2_env && " + " ".join(command)
            logger.info(" - the command is: ")
            logger.info(command_str)
            # Run the command inside the container
            result = container.exec_run(["bash", "-c", command_str])
            logger.info(result.output)

            SequencingAnalysis.update_field(analysis_id, "status", "Finished")
            SequencingAnalysis.update_field(
                analysis_id, "result", result.output
            )

        elif region == "SSU":
            # We used to define the container differently
            # because we had two different versions of lotus2
            container = client.containers.get("spun-lotus2")
            clustering_method = "dada2"
            if clustering == "vsearch":
                clustering_method = "vsearch"

            # The following two is if we want to use
            # The FULL SILVA database
            refDB = (
                "/lotus2_files/vt_types_fasta_from_05-06-2019.qiime.fasta,SLV"
            )

            tax4refDB = "/lotus2_files/vt_types_GF.txt"

            # The following two is if we want to use
            # The reduced SILVA database
            refDB = (
                "/lotus2_files/vt_types_fasta_from_05-06-2019.qiime.fasta,"
                "/lotus2_files/SLV_138.1_SSU_NO_AMF.fasta"
            )

            tax4refDB = (
                "/lotus2_files/vt_types_GF.txt,"
                "/lotus2_files/SLV_138.1_SSU_NO_AMF.tax"
            )

            sdmopt = (
                "/home/condauser/miniconda/envs/lotus2_env/share/"
                "lotus2-2.34.1-0/configs/sdm_miSeq2.txt"
            )
            mapping_file = input_dir + "/mapping_files/SSU_Mapping.txt"

            logger.info(" - Here we will try the command")
            command = [
                "lotus2",
                debug_command,
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
                clustering_method,
                "-LCA_cover",
                "0.97",
                "-derepMin",
                "10:1,5:2,3:3",
                "-sdmopt",
                sdmopt,
            ]
            command_str = "source activate lotus2_env && " + " ".join(command)
            logger.info(" - the command is: ")
            logger.info(command_str)
            # Run the command inside the container
            result = container.exec_run(["bash", "-c", command_str])
            logger.info(result.output)

            SequencingAnalysis.update_field(analysis_id, "status", "Finished")
            SequencingAnalysis.update_field(
                analysis_id, "result", result.output
            )

        else:
            logger.info(
                "Lotus2 report generation for amplicon "
                + region
                + " cannot be generated as we don't have the details."
            )
            SequencingAnalysis.update_field(
                analysis_id, "status", "Abandoned. Unknown region."
            )

    except Exception as e:
        logger.error(f"Error generating Lotus2 report: {str(e)}")
        SequencingAnalysis.update_field(
            analysis_id, "status", "Error while generating."
        )
        SequencingAnalysis.update_field(analysis_id, "result", str(e))


def delete_generated_lotus2_report(region_nr, process_id, input_dir, region):
    sequencing_analysis_type = get_analysis_type(region)

    from models.sequencing_analysis import SequencingAnalysis

    if sequencing_analysis_type != 0:
        analysis_id = SequencingAnalysis.create(
            process_id, sequencing_analysis_type
        )

        if analysis_id:
            SequencingAnalysis.update_field(
                analysis_id, "celery_task_id", None
            )
            SequencingAnalysis.update_field(analysis_id, "updated_at", None)
            SequencingAnalysis.update_field(analysis_id, "status", None)
            SequencingAnalysis.update_field(analysis_id, "result", None)

    # TO DO: the path should be from the SequencingAnalysis name
    output_path = input_dir + "/lotus2_report/" + region
    if os.path.exists(output_path) and os.path.isdir(output_path):
        shutil.rmtree(output_path)

    return {"msg": "Process initiated"}


def get_analysis_type(region):
    sequencing_analysis_type = 0
    if region == "SSU":
        sequencing_analysis_type = 1
    elif region == "ITS2":
        sequencing_analysis_type = 3
    elif region == "ITS1":
        sequencing_analysis_type = 4
    return sequencing_analysis_type
