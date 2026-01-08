import docker
import logging
import shutil
import os
from datetime import datetime
from helpers.hetzner_vm import run_lotus3_on_vm

# Note: Even though for legacy reasons the module
# and all the variables and field names are called lotus2,
# we are actually using lotus3 for the report generation.

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def init_generate_lotus2_report(
    process_id,
    input_dir,
    region,
    debug=False,
    analysis_type_id="0",
    parameters={},
):
    from tasks import generate_lotus2_report_async

    from models.sequencing_analysis import SequencingAnalysis

    if analysis_type_id != 0:
        analysis_id = SequencingAnalysis.create(process_id, analysis_type_id)
        analysis = SequencingAnalysis.get(analysis_id)
        status = analysis.lotus2_status
        if status is None:
            try:
                result = generate_lotus2_report_async.delay(
                    process_id,
                    input_dir,
                    region,
                    debug,
                    analysis_type_id,
                    parameters,
                )
                logger.info(
                    f"Celery generate_lotus2_report_async task "
                    f"called successfully! Task ID: {result.id}"
                )

                if analysis_id != 0:
                    SequencingAnalysis.update_field(
                        analysis_id, "lotus2_celery_task_id", result.id
                    )

            except Exception as e:
                logger.error(
                    "This is an error message from helpers/bucket.py "
                    " while trying to generate_lotus2_report_async"
                )
                logger.error(e)
                return {
                    "error": (
                        "This is an error message from helpers/lotus2.py "
                        " while trying to generate_lotus2_report_async"
                    ),
                    "e": (e),
                }
            return {"msg": "Process initiated"}
        else:
            return {
                "msg": "Cannot initiate the process as there is already one"
            }
    else:
        return {"error": "Wrong analysis type ID"}


def generate_lotus2_report(
    process_id, input_dir, region, debug, analysis_type_id, parameters
):
    import os

    client = docker.from_env()

    from models.sequencing_analysis import SequencingAnalysis
    from models.sequencing_analysis_type import SequencingAnalysisType
    from models.app_configuration import AppConfiguration

    def log(msg):
        logger.info(msg)

    # Normalize input_dir (ensure leading slash)
    input_dir = os.path.join("/", input_dir)

    # Fetch database objects
    analysis_id = SequencingAnalysis.get_by_upload_and_type(
        process_id, analysis_type_id
    )
    analysis_type = SequencingAnalysisType.get(analysis_type_id)

    # Initial DB updates
    SequencingAnalysis.update_field(
        analysis_id, "lotus2_started_at", datetime.utcnow()
    )
    SequencingAnalysis.update_field(analysis_id, "lotus2_status", "Started")
    SequencingAnalysis.update_field(analysis_id, "parameters", parameters)

    output_path = os.path.join(input_dir, "lotus2_report", analysis_type.name)

    # Logging block
    log("Trying for:")
    for k, v in {
        "process_id": process_id,
        "analysis_type_id": analysis_type_id,
        "analysis_id": analysis_id,
        "input_dir": input_dir,
        "output_path": output_path,
        "region": region,
        "debug": debug,
        "parameters": parameters,
    }.items():
        log(f" - {k}: {v}")

    debug_flag = " -v --debug " if debug == 1 else ""

    try:
        container = client.containers.get("spun-lotus3")

        # ------------------------------
        #  Helper: Run command + DB write
        # ------------------------------
        def run_lotus_command(command_list, server_size):
            command_str = " ".join(command_list)
            log(" - the command is:")
            log(command_str)

            # Store the command in DB
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_command", command_str
            )

            remote_pipeline = AppConfiguration.get_value("remote_pipeline")

            # -------------------------------------------------------
            # REMOTE PIPELINE LOGIC
            # -------------------------------------------------------
            if str(remote_pipeline) == "1":
                log("Remote pipeline enabled → starting VM...")
                server_name = f"lotus3-{process_id}-{analysis_type_id}-{int(datetime.utcnow().timestamp())}"
                # When on the VM set temp dirs to be inside the VM.
                # Set all 3 variables because different tools use different ones.
                command_str = (
                    "export TMPDIR=/tmp/lotus_tmp && "
                    "export TMP=/tmp/lotus_tmp && "
                    "export TEMP=/tmp/lotus_tmp && "
                    "mkdir -p /tmp/lotus_tmp && " + command_str
                )

                result = run_lotus3_on_vm(
                    command_str, server_name, server_size
                )

                SequencingAnalysis.update_field(
                    analysis_id,
                    "lotus2_result",
                    result["stdout"] + "\n" + result["stderr"],
                )
                SequencingAnalysis.update_field(
                    analysis_id, "lotus2_status", "Finished"
                )
                SequencingAnalysis.update_field(
                    analysis_id, "lotus2_finished_at", datetime.utcnow()
                )

                return

            # -------------------------------------------------------
            # NORMAL LOCAL DOCKER EXECUTION
            # -------------------------------------------------------
            result = container.exec_run(["bash", "-c", command_str])
            log(result.output)

            SequencingAnalysis.update_field(
                analysis_id, "lotus2_status", "Finished"
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", datetime.utcnow()
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_result", result.output
            )

        # ------------------------------
        #          REGION = ITS1/ITS2
        # ------------------------------
        if region in ["ITS1", "ITS2"]:
            server_size = "cpx62"
            mapping_file = os.path.join(
                input_dir, "mapping_files", f"{region}_Mapping.txt"
            )

            # Select SDM file
            sdm_map = {
                "sdm_miSeq_ITS_200": "/lotus2_files/sdm_miSeq_ITS_200.txt",
                "sdm_miSeq_ITS_forward": "/lotus2_files/sdm_miSeq_ITS_forward.txt",
            }
            sdmopt = sdm_map.get(
                parameters.get("sdmopt"), "/lotus2_files/sdm_miSeq_ITS.txt"
            )

            # refDB / tax4refDB selection
            if analysis_type.name in ["ITS1", "ITS2"]:
                refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.fasta"
                tax4refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.tax"
            else:  # eukaryome
                refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4.fasta"
                tax4refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4_lotus.tax"
                server_size = "ccx43"

            cmd = [
                "lotus3",
                debug_flag,
                "-i",
                input_dir,
                "-o",
                output_path,
                "-m",
                mapping_file,
                "-refDB",
                refDB,
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
                "-sdmThreads",
                "1",
                "-sdmopt",
                sdmopt,
                "-id",
                "0.97",
                "-tax4refDB",
                tax4refDB,
            ]
            return run_lotus_command(cmd, server_size)

        # ------------------------------
        #            REGION = SSU
        # ------------------------------
        if region == "SSU":
            parameters = parameters | analysis_type.parameters
            clustering = parameters["clustering"]
            server_size = "cpx62"

            mapping_file = os.path.join(
                input_dir, "mapping_files", "SSU_Mapping.txt"
            )

            sdm_map = {
                "sdm_miSeq2_250": "/lotus2_files/sdm_miSeq2_250.txt",
            }
            sdmopt = sdm_map.get(
                parameters.get("sdmopt"),
                "/lotus2_files/sdm_miSeq2_SSU_Spun.txt",
            )

            # Select DBs
            if analysis_type.name in ["SSU_dada2", "SSU_vsearch"]:
                # Reduced SILVA
                refDB = (
                    "/lotus2_files/vt_types_fasta_from_05-06-2019.qiime.fasta,"
                    "/lotus2_files/SLV_138.1_SSU_NO_AMF.fasta"
                )
                tax4refDB = (
                    "/lotus2_files/vt_types_GF.txt,"
                    "/lotus2_files/SLV_138.1_SSU_NO_AMF.tax"
                )

            elif analysis_type.name == "SSU_eukaryome":
                refDB = "/lotus2_files/mothur_EUK_SSU_v1.9.3.fasta"
                tax4refDB = "/lotus2_files/mothur_EUK_SSU_v1.9.3_lotus.tax"
                server_size = "ccx43"

            cmd = [
                "lotus3",
                debug_flag,
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
                clustering,
                "-LCA_cover",
                "0.97",
                "-sdmThreads",
                "1",
                "-derepMin",
                "10:1,5:2,3:3",
                "-sdmopt",
                sdmopt,
            ]
            return run_lotus_command(cmd, server_size)

        # ------------------------------
        #       REGION = Full ITS
        # ------------------------------
        if region == "Full_ITS":
            server_size = "cpx62"
            mapping_file = os.path.join(
                input_dir, "mapping_files", "Full_ITS_Mapping.txt"
            )

            if analysis_type.name in ["FULL_ITS_UNITE", "FULL_ITS_Eukaryome"]:
                sdmopt = "/lotus2_files/sdm_PacBio_ITS.txt"

                if analysis_type.name == "FULL_ITS_UNITE":
                    refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.fasta"
                    tax4refDB = "/lotus2_files/UNITE_v10_sh_general_release_dynamic_all_19.02.2025.tax"
                else:
                    refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4.fasta"
                    tax4refDB = "/lotus2_files/mothur_EUK_ITS_v1.9.4_lotus.tax"

                cmd = [
                    "lotus3",
                    debug_flag,
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
                    "ITS",
                    "-LCA_idthresh",
                    "97,95,93,91,88,78,0",
                    "-tax_group",
                    "fungi",
                    "-taxAligner",
                    "blast",
                    "-clustering",
                    "vsearch",
                    "-LCA_cover",
                    "0.97",
                    "-sdmThreads",
                    "1",
                    "-derepMin",
                    "10:1,5:2,3:3",
                    "-sdmopt",
                    sdmopt,
                ]
                return run_lotus_command(cmd, server_size)

            # Unsupported Full ITS type
            SequencingAnalysis.update_field(
                analysis_id,
                "lotus2_status",
                "Abandoned. Full_ITS without supported analysis.",
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", datetime.utcnow()
            )
            log("Unsupported Full_ITS analysis.")
            return

        # ------------------------------
        # UNKNOWN REGION
        # ------------------------------
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_status", "Abandoned. Unknown region."
        )
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_finished_at", datetime.utcnow()
        )
        log(f"Unknown region {region}")

    except Exception as e:
        logger.error(f"Error generating Lotus2 report: {str(e)}")
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_status", "Error while generating."
        )
        SequencingAnalysis.update_field(
            analysis_id, "lotus2_finished_at", datetime.utcnow()
        )
        SequencingAnalysis.update_field(analysis_id, "lotus2_result", str(e))


def delete_generated_lotus2_report(process_id, input_dir, analysis_type_id):

    if analysis_type_id != 0:
        from models.sequencing_analysis import SequencingAnalysis
        from models.sequencing_analysis_type import SequencingAnalysisType

        analysis_type = SequencingAnalysisType.get(analysis_type_id)

        analysis_id = SequencingAnalysis.get_by_upload_and_type(
            process_id, analysis_type_id
        )

        if analysis_id:

            SequencingAnalysis.update_field(
                analysis_id, "lotus2_celery_task_id", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_started_at", None
            )
            SequencingAnalysis.update_field(
                analysis_id, "lotus2_finished_at", None
            )
            SequencingAnalysis.update_field(analysis_id, "lotus2_status", None)
            SequencingAnalysis.update_field(analysis_id, "lotus2_result", None)

            output_path = input_dir + "/lotus2_report/" + analysis_type.name
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


def init_generate_all_lotus2_reports(analysis_type_id, from_id, to_id):
    from tasks import generate_all_lotus2_reports_async

    generate_all_lotus2_reports_async.delay(analysis_type_id, from_id, to_id)


def generate_all_lotus2_reports(analysis_type_id, from_id, to_id):
    from models.sequencing_upload import SequencingUpload
    from models.sequencing_analysis import SequencingAnalysis

    processes_data = SequencingUpload.get_all()
    from_id = int(from_id)
    to_id = int(to_id)

    for process_data in processes_data:
        process_id = process_data["id"]
        # Check if the process_id satisfies the given conditions
        if (
            (from_id is None and to_id is None)
            or (
                from_id is not None and to_id is None and process_id >= from_id
            )
            or (from_id is None and to_id is not None and process_id <= to_id)
            or (
                from_id is not None
                and to_id is not None
                and from_id <= process_id <= to_id
            )
        ):
            for region_type, analysis_list in process_data["analysis"].items():
                for analysis in analysis_list:
                    if str(analysis_type_id) == str(
                        analysis["analysis_type_id"]
                    ):
                        # Get the fresh status from the database
                        analysis_id = SequencingAnalysis.create(
                            process_id, analysis_type_id
                        )
                        analysis = SequencingAnalysis.get(analysis_id)
                        status = analysis.lotus2_status

                        # Only proceed if the status is None
                        if status is None:
                            input_dir = (
                                "seq_processed/"
                                + process_data["uploads_folder"]
                            )
                            generate_lotus2_report(
                                process_id=process_data["id"],
                                input_dir=input_dir,
                                region=region_type,
                                debug=False,
                                analysis_type_id=analysis_type_id,
                                parameters={},
                            )
                            logger.info(
                                "inside generate_all_lotus2_reports . "
                                + " The analysis_id is "
                                + str(analysis_id)
                            )
