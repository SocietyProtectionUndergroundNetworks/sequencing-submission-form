import docker
import logging
import shutil
import os
import json
import shlex
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from urllib.request import pathname2url
from pdf2image import convert_from_path

# PROCESS_DIR =
logger = logging.getLogger("my_app_logger")


def format_lotus_command(command_string):
    """Replicates the R formatting logic for display."""
    if not command_string:
        return "N/A"

    # 1. Clean up whitespace
    # Handles multi-line commands by joining, stripping, and normalizing spaces
    formatted_command = " ".join(command_string.split()).strip()

    # 2. Add line breaks and tabs before arguments (e.g., -p becomes \ \n\t-p)
    formatted_command = formatted_command.replace(" -", " \\\n\t-")

    # 3. Add line breaks after commas followed by paths
    formatted_command = formatted_command.replace(",/", ",\\\n\t/")

    return formatted_command


def make_file_uri(app_root, relative_path):
    """Creates a file:/// URI from the absolute app root and the file's relative path."""
    if not relative_path:
        return ""
    # 1. Combine app root and relative path to get the full absolute file system path
    absolute_path = os.path.join(app_root, relative_path)
    # 2. Convert the absolute path to a URL-encoded file URI
    return f'file:///{pathname2url(absolute_path).lstrip("/")}'


def make_pdf_to_png(pdf_path):
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        return None
    png_file = pdf_path.replace(".pdf", ".png")
    pages = convert_from_path(pdf_path, dpi=150)
    pages[0].save(png_file, "PNG")
    return png_file


def create_pdf_report(process_id):
    from models.sequencing_upload import SequencingUpload
    from models.sequencing_analysis import SequencingAnalysis

    # check if we have ITS2, ITS1, SSU_DADA analysis ready.
    process_data = SequencingUpload.get(process_id)
    uploads_folder = process_data["uploads_folder"]
    project_id = process_data["project_id"]

    # Delete unused temp dir logic
    # temp_dir_path = os.path.join("seq_processed/", str(uploads_folder), "temp")
    # os.makedirs(temp_dir_path, exist_ok=True)

    rscripts_reports = SequencingUpload.check_rscripts_reports_exist(
        process_id
    )

    its_report = None
    ssu_report = None
    missing_samples_its = None
    missing_samples_ssu = None
    its_command = None
    ssu_command = None
    its_region = None
    ssu_region = None
    its_count_ecm = 0
    ssu_count_amf = 0

    for r_report in rscripts_reports:
        if r_report["analysis_type"] in ("ITS1", "ITS2"):
            its_report = r_report["analysis_type"]
            missing_samples_its = SequencingUpload.get_missing_its_files(
                process_id
            )
            its_command = r_report["lotus2_command"]
            its_region = r_report.get("region", "ITS")  # Use get for safety
            its_count_ecm = SequencingAnalysis.get_ecm_count(r_report["id"])
        elif "FULL_ITS_Eukaryome" == r_report["analysis_type"]:
            its_report = r_report["analysis_type"]
            missing_samples_its = SequencingUpload.get_missing_its_files(
                process_id
            )
            its_command = r_report["lotus2_command"]
            its_region = r_report["region"]
            its_count_ecm = SequencingAnalysis.get_ecm_count(r_report["id"])

        elif "SSU_dada2" == r_report["analysis_type"]:
            ssu_report = r_report["analysis_type"]
            missing_samples_ssu = SequencingUpload.get_missing_ssu_files(
                process_id
            )
            ssu_command = r_report["lotus2_command"]
            ssu_region = r_report["region"]
            ssu_count_amf = SequencingAnalysis.get_amf_count(r_report["id"])

    # Set up global path variables
    app_root = os.path.abspath(".")
    base_data_path = os.path.join(app_root, "seq_processed", uploads_folder)

    # --- 2. Prepare Data for Jinja ---

    its_contaminants_csv_rel_path = (
        os.path.join(
            base_data_path, "r_output", its_report, "contaminants.csv"
        )
        if its_report
        else ""
    )
    ssu_contaminants_csv_rel_path = (
        os.path.join(
            base_data_path, "r_output", ssu_report, "contaminants.csv"
        )
        if ssu_report
        else ""
    )
    # Calculate RELATIVE paths for use in make_file_uri
    its_plots = {
        "library_size": os.path.join(
            base_data_path, "r_output", its_report or "", "LibrarySize.pdf"
        ),
        "qc_plot": os.path.join(
            base_data_path,
            "fastqc",
            its_region or "",
            "multiqc_plots/png/mqc_fastqc_per_base_sequence_quality_plot_1.png",
        ),
        "rarefaction": os.path.join(
            base_data_path,
            "r_output",
            its_report or "",
            "filtered_rarefaction.pdf",
        ),
        "ecm_plot": os.path.join(
            base_data_path,
            "r_output",
            its_report or "",
            "ecm_physeq_by_genus.pdf",
        ),
    }
    ssu_plots = {
        "library_size": os.path.join(
            base_data_path, "r_output", ssu_report or "", "LibrarySize.pdf"
        ),
        "qc_plot": os.path.join(
            base_data_path,
            "fastqc",
            ssu_region or "",
            "multiqc_plots/png/mqc_fastqc_per_base_sequence_quality_plot_1.png",
        ),
        "rarefaction": os.path.join(
            base_data_path,
            "r_output",
            ssu_report or "",
            "filtered_rarefaction.pdf",
        ),
        "amf_plot": os.path.join(
            base_data_path,
            "r_output",
            ssu_report or "",
            "amf_physeq_by_genus.pdf",
        ),
    }

    if its_report is not None:
        its_plots["library_size"] = make_pdf_to_png(its_plots["library_size"])
        its_plots["rarefaction"] = make_pdf_to_png(its_plots["rarefaction"])
        its_plots["ecm_plot"] = make_pdf_to_png(its_plots["ecm_plot"])

    if ssu_report is not None:
        ssu_plots["library_size"] = make_pdf_to_png(ssu_plots["library_size"])
        ssu_plots["rarefaction"] = make_pdf_to_png(ssu_plots["rarefaction"])
        ssu_plots["amf_plot"] = make_pdf_to_png(ssu_plots["amf_plot"])

    report_data = {
        # General Info
        "project_name": project_id,
        "sequencing_platform": process_data["Sequencing_platform"],
        "its_region": its_region,
        "ssu_region": ssu_region,
        "base_data_path": base_data_path,
        # ITS Data
        "its_analysis_exists": its_report is not None,
        "missing_samples_its": missing_samples_its,
        "its_formatted_command": format_lotus_command(its_command),
        "its_contaminants_file_exists": os.path.exists(
            os.path.join(app_root, its_contaminants_csv_rel_path)
        ),
        # FIX: Plot Paths are now full file:/// URIs
        "its_library_size_plot": make_file_uri(
            app_root, its_plots["library_size"]
        ),
        "its_qc_plot": make_file_uri(app_root, its_plots["qc_plot"]),
        "its_rarefaction_plot": make_file_uri(
            app_root, its_plots["rarefaction"]
        ),
        "its_ecm_plot_path": make_file_uri(app_root, its_plots["ecm_plot"]),
        # SSU Data
        "ssu_analysis_exists": ssu_report is not None,
        "missing_samples_ssu": missing_samples_ssu,
        "ssu_formatted_command": format_lotus_command(ssu_command),
        "ssu_contaminants_file_exists": os.path.exists(
            os.path.join(app_root, ssu_contaminants_csv_rel_path)
        ),
        "ssu_count_amf": ssu_count_amf,
        "ssu_library_size_plot": make_file_uri(
            app_root, ssu_plots["library_size"]
        ),
        "ssu_qc_plot": make_file_uri(app_root, ssu_plots["qc_plot"]),
        "ssu_rarefaction_plot": make_file_uri(
            app_root, ssu_plots["rarefaction"]
        ),
        "ssu_amf_plot_path": make_file_uri(app_root, ssu_plots["amf_plot"]),
        "its_count_ecm": its_count_ecm,
    }

    # --- 3. Template Rendering and PDF Generation ---

    # Template path lookup (assuming function is in a helper dir)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    app_root_dir = os.path.dirname(current_file_dir)
    template_dir = os.path.join(app_root_dir, "templates")

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("pdf_report.html")

    # 3.2 Render the HTML
    html_output = template.render(report_data)

    # 3.3 Define output paths
    output_path = os.path.join(
        app_root, base_data_path, "r_output", "report.pdf"
    )

    # 3.4 Generate PDF using WeasyPrint
    try:
        # We rely on the full file:/// URI in the template and the url_fetcher for access
        HTML(string=html_output, base_url=os.path.abspath(".")).write_pdf(
            output_path
        )
        logger.info(f"PDF report created successfully at: {output_path}")
    except Exception as e:
        logger.error(
            f"Error generating PDF with WeasyPrint: {e}", exc_info=True
        )

    # create the symlinks
    SequencingUpload.create_symlinks(process_id)


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

        if region in ["ITS1", "ITS2", "Full_ITS", "Full_ITS_LSU"]:
            r_script = "EcM_decontam_taxonomic_filtering.R"

        if region in ["SSU"]:
            r_script = "AMF_decontam_taxonomic_filtering.R"

        if region in ["ITS1", "ITS2", "SSU", "Full_ITS", "Full_ITS_LSU"]:
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
                    generate_rscripts_report(
                        process_data["id"], input_dir, region, analysis_type_id
                    )
