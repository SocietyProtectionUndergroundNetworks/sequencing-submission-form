import os
import multiqc
import subprocess
import zipfile
from pathlib import Path
from helpers.bucket import bucket_upload_folder_v2, bucket_chunked_upload_v2

import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def create_fastqc_report(fastq_file, input_folder, bucket, region):
    output_folder = os.path.join(input_folder, "fastqc")
    os.makedirs(output_folder, exist_ok=True)
    input_file = os.path.join(input_folder, fastq_file)
    output_folder_of_file = os.path.join(output_folder, region)
    Path(output_folder_of_file).mkdir(parents=True, exist_ok=True)
    input_file = os.path.join(input_folder, fastq_file)
    fastqc_cmd = (
        f"/usr/local/bin/FastQC/fastqc "
        f"--memory 2048 "
        f"-o '{output_folder_of_file}' "
        f"'{input_file}'"
    )
    subprocess.run(fastqc_cmd, shell=True, executable="/bin/bash")


def init_create_fastqc_report(fastq_file, input_folder, bucket, region):

    from tasks import create_fastqc_report_async

    try:
        result = create_fastqc_report_async.delay(
            fastq_file, input_folder, bucket, region
        )
        logger.info(
            "Celery create_fastqc_report task called successfully! "
            f"Task ID: {result.id}"
        )
    except Exception as e:
        logger.error("This is an error message from fastqc.py")
        logger.error(e)


def check_fastqc_report(filename, region, upload_folder, return_format="html"):
    logger = logging.getLogger(__name__)

    if filename:
        # Only process files that end with fastq.gz or fq.gz
        if not (filename.endswith("fastq.gz") or filename.endswith("fq.gz")):
            logger.info(
                "File does not end with fastq.gz or fq.gz, returning False."
            )
            return False

        # Sanitize the filename by removing the .gz extension
        if filename.endswith(".fastq.gz"):
            base_filename = filename.rsplit(".fastq.gz", 1)[
                0
            ]  # Remove the .fastq.gz suffix
        elif filename.endswith(".fq.gz"):
            base_filename = filename.rsplit(".fq.gz", 1)[
                0
            ]  # Remove the .fq.gz suffix
        else:
            # If the filename doesn't match expected extensions, return False
            return False

        # Avoid appending extra underscores by
        # checking if the filename already has '_fastqc'
        if not base_filename.endswith("_fastqc"):
            base_filename += "_fastqc"

        # Define the paths for the FastQC report files
        html_file = (
            f"seq_processed/{upload_folder}/fastqc/{region}/"
            f"{base_filename}.html"
        )
        zip_file = (
            f"seq_processed/{upload_folder}/fastqc/{region}/"
            f"{base_filename}.zip"
        )

        # Convert relative paths to absolute paths
        abs_html_file = os.path.abspath(html_file)
        abs_zip_file = os.path.abspath(zip_file)

        # Check if both files exist
        if os.path.isfile(abs_html_file) and os.path.isfile(abs_zip_file):
            if return_format == "zip":
                return abs_zip_file
            else:
                return abs_html_file

    # If either of the files doesn't exist, return False
    return False


def create_multiqc_report(process_id):
    from models.sequencing_upload import SequencingUpload

    process_data = SequencingUpload.get(process_id)

    uploads_folder = process_data["uploads_folder"]
    bucket = process_data["project_id"]

    if process_data["regions"]:
        for region in process_data["regions"]:
            multiqc_folder = os.path.join(
                "seq_processed", uploads_folder, "fastqc", region
            )
            # The 'export_plots=True' only works in
            # multiqc version 1.19, not in 1.25.2
            multiqc.run(
                multiqc_folder, outdir=multiqc_folder, export_plots=True
            )
            bucket_upload_directory = (
                region + "/MultiQC_report/" + uploads_folder
            )
            # upload the html file

            bucket_chunked_upload_v2(
                local_file_path=multiqc_folder + "/multiqc_report.html",
                destination_upload_directory=bucket_upload_directory,
                destination_blob_name="multiqc_report.html",
                sequencer_file_id=None,
                bucket_name=bucket,
                known_md5=None,
            )

            bucket_upload_directory = bucket_upload_directory + "/multiqc_data"
            # and upload the folder of the report contents
            bucket_upload_folder_v2(
                folder_path=multiqc_folder + "/multiqc_data",
                destination_upload_directory=bucket_upload_directory,
                bucket=bucket,
            )
    else:
        logger.info("There are no regions!")


def init_create_multiqc_report(process_id):

    from tasks import create_multiqc_report_async

    try:
        result = create_multiqc_report_async.delay(process_id)
        logger.info(
            "Celery create_multiqc_report task called successfully! "
            f"Task ID: {result.id}"
        )
    except Exception as e:
        logger.error("This is an error message from fastqc.py")
        logger.error(e)


def check_multiqc_report(process_id):
    from models.sequencing_upload import SequencingUpload

    # Fetch process data from SequencingUpload model
    process_data = SequencingUpload.get(process_id)

    # Extract uploads folder and project id from process data
    uploads_folder = process_data["uploads_folder"]

    # Check if regions are specified
    if process_data["regions"]:
        # Iterate through each region
        for region in process_data["regions"]:
            # Construct the path to the multiqc folder
            multiqc_folder = os.path.join(
                "seq_processed", uploads_folder, "fastqc", region
            )

            # Construct the path to the potential multiqc report file
            multiqc_report_file = os.path.join(
                multiqc_folder, "multiqc_report.html"
            )

            # Check if the multiqc report file exists
            if not os.path.isfile(multiqc_report_file):
                # If any report does not exist, return False immediately
                return False

        # If all reports exist, return True
        return True

    else:
        # If there are no regions specified, we can assume reports do not exist
        return False


def extract_total_sequences_from_fastqc_zip(abs_zip_path):
    """
    Extract the 'Total Sequences' value from a FastQC .zip
    report using its absolute path
    without unzipping it.

    :param abs_zip_path: Absolute path to the FastQC .zip report.
    :return: Total Sequences value (int) or None if not found.
    """
    if not os.path.isabs(abs_zip_path):
        logger.info(
            f"The provided path is not an absolute path: {abs_zip_path}"
        )
        return None

    if not os.path.exists(abs_zip_path):
        logger.info(f"File not found: {abs_zip_path}")
        return None

    total_sequences = None
    fastqc_data_filename = "fastqc_data.txt"
    try:
        with zipfile.ZipFile(abs_zip_path, "r") as zip_ref:
            # Find the file 'fastqc_data.txt' within any folder inside the zip
            fastqc_data_path = None
            for file_name in zip_ref.namelist():
                if file_name.endswith(fastqc_data_filename):
                    fastqc_data_path = file_name
                    break

            if fastqc_data_path:
                # Read the fastqc_data.txt content
                with zip_ref.open(fastqc_data_path) as fastqc_data_file:
                    for line in fastqc_data_file:
                        line = line.decode("utf-8")  # Convert bytes to string
                        # Find the line that starts with 'Total Sequences'
                        if line.startswith("Total Sequences"):
                            total_sequences = int(line.split("\t")[1].strip())
                            break
            else:
                logger.info(
                    f"{fastqc_data_filename} not found in the zip archive."
                )
    except zipfile.BadZipFile:
        logger.info(f"Error: {abs_zip_path} is not a valid zip file.")
    except Exception as e:
        logger.info(
            f"An error occurred while reading the FastQC report zip: {e}"
        )

    return total_sequences
