import os
import multiqc
import subprocess
import json
from pathlib import Path
from models.upload import Upload
from helpers.bucket import bucket_upload_folder, bucket_chunked_upload

import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def get_multiqc_report(process_id, bucket, folder):
    upload = Upload.get(process_id)

    extract_directory = upload.extract_directory

    fastqc_path = os.path.join(extract_directory, "fastqc", bucket, folder)

    multiqc_report_exists = os.path.exists(
        os.path.join(fastqc_path, "multiqc_report.html")
    )
    to_return = {
        "multiqc_report_exists": multiqc_report_exists,
        "multiqc_report_path": fastqc_path,
    }

    return to_return


def get_fastqc_progress(process_id):
    upload = Upload.get(process_id)
    files_dict_db = upload.get_files_json()

    count_fastq_gz = 0
    progress_text = ""
    process_finished = 0

    extract_directory = upload.extract_directory
    fastqc_process_id = upload.fastqc_process_id

    fastqc_path = os.path.join(extract_directory, "fastqc")

    from tasks import fastqc_multiqc_files_async

    task = fastqc_multiqc_files_async.AsyncResult(fastqc_process_id)

    if not task.ready():
        # count the files we should have
        files_main = os.listdir(extract_directory)
        count_fastq_gz = sum(
            1
            for file in files_main
            if (
                (file.endswith(".fastq.gz") or file.endswith(".fastq"))
                and not (file.startswith("._"))
            )
        )

        # Get how many are done
        progress_text = upload.fastqc_files_progress
    else:
        process_finished = 1
        upload.mark_field_as_true(process_id, "fastqc_run")

    multiqc_report_exists = os.path.exists(
        os.path.join(fastqc_path, "multiqc_report.html")
    )

    to_return = {
        "process_finished": process_finished,
        "files_main": count_fastq_gz,
        "progress_text": progress_text,
        "multiqc_report_exists": multiqc_report_exists,
        "multiqc_report_path": fastqc_path,
        "files_dict_db": files_dict_db,
    }

    return to_return


def init_fastqc_multiqc_files(process_id):

    upload = Upload.get(process_id)
    from tasks import fastqc_multiqc_files_async

    try:
        result = fastqc_multiqc_files_async.delay(process_id)
        logger.info(
            f"Celery multiqc task called successfully! Task ID: {result.id}"
        )
        task_id = result.id
        upload.update_fastqc_process_id(process_id, task_id)
    except Exception as e:
        logger.error("This is an error message from upload.py")
        logger.error(e)


def fastqc_multiqc_files(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    input_folder = str(upload.extract_directory)
    files_json = json.loads(upload.files_json)

    if upload.renaming_skipped:
        new_files_json = {
            key: {
                "bucket": data.get("bucket"),
                "folder": data.get("folder"),
                "old_filename": key,
            }
            for key, data in files_json.items()
            if "bucket" in data and "folder" in data
        }
    else:
        new_files_json = {
            data["new_filename"]: {
                "bucket": data.get("bucket"),
                "folder": data.get("folder"),
                "old_filename": key,
            }
            for key, data in files_json.items()
            if "bucket" in data and "folder" in data
        }

    results = []
    output_folder = os.path.join(input_folder, "fastqc")
    os.makedirs(output_folder, exist_ok=True)
    output_folders = {}
    nr_output_folders = 0
    files_done = 0

    fastq_files = [
        f
        for f in os.listdir(input_folder)
        if (
            (f.endswith(".fastq.gz") or f.endswith(".fastq"))
            and not f.startswith(".")
        )
    ]
    nr_files = len(fastq_files)
    for fastq_file in fastq_files:
        if fastq_file in new_files_json:
            bucket = new_files_json[fastq_file]["bucket"]
            folder = new_files_json[fastq_file]["folder"]

            if bucket not in output_folders:
                output_folders[bucket] = {}

            if folder not in output_folders[bucket]:
                output_folders[bucket][folder] = True
                nr_output_folders += 1

            create_fastqc_report(fastq_file, input_folder, bucket, folder)

            files_done += 1
            progress = (
                str(files_done) + " fastq files done out of " + str(nr_files)
            )
            if nr_files == files_done:
                progress = progress + ". Starting creation of multiqc reports"
            Upload.update_fastqc_files_progress(process_id, progress)

    # Run the multiqc process differently for each project.
    multiqc_done = 0
    for bucket, folders in output_folders.items():
        for folder in folders:
            multiqc_folder = os.path.join(output_folder, bucket, folder)
            multiqc.run(multiqc_folder, outdir=multiqc_folder)
            fastq_files_to_delete = [
                f
                for f in os.listdir(multiqc_folder)
                if f.endswith("_fastqc.html") or f.endswith("_fastqc.zip")
            ]
            for file_to_delete in fastq_files_to_delete:
                path_to_delete = os.path.join(multiqc_folder, file_to_delete)
                os.remove(path_to_delete)

            bucket_upload_folder(
                multiqc_folder,
                folder + "/MultiQC_report/" + uploads_folder,
                process_id,
                "fastqc_files",
                bucket,
            )

            multiqc_done = multiqc_done + 1
            progress = (
                str(multiqc_done)
                + " multiqc reports done out of "
                + str(nr_output_folders)
            )
            Upload.update_fastqc_files_progress(process_id, progress)

    Upload.mark_field_as_true(process_id, "fastqc_sent_to_bucket")

    results.append("Finished")
    return results


def create_fastqc_report(fastq_file, input_folder, bucket, region):
    output_folder = os.path.join(input_folder, "fastqc")
    os.makedirs(output_folder, exist_ok=True)
    input_file = os.path.join(input_folder, fastq_file)
    output_folder_of_file = os.path.join(output_folder, bucket, region)
    Path(output_folder_of_file).mkdir(parents=True, exist_ok=True)
    input_file = os.path.join(input_folder, fastq_file)
    fastqc_cmd = (
        f"/usr/local/bin/FastQC/fastqc "
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


def check_fastqc_report(filename, bucket, region, upload_folder):
    logger = logging.getLogger(__name__)

    if filename:
        # Only process files that end with fastq.gz
        if not filename.endswith("fastq.gz"):
            logger.info("File does not end with fastq.gz, returning False.")
            return False

        # Sanitize the filename by removing the .gz extension
        # and replacing other unwanted characters
        base_filename = filename.rsplit(".fastq.gz", 1)[0] + "_fastqc"

        # Define the paths for the FastQC report files
        html_file = (
            f"seq_processed/{upload_folder}/fastqc/{bucket}/{region}/"
            f"{base_filename}.html"
        )
        zip_file = (
            f"seq_processed/{upload_folder}/fastqc/{bucket}/{region}/"
            f"{base_filename}.zip"
        )

        # Convert relative paths to absolute paths
        abs_html_file = os.path.abspath(html_file)
        abs_zip_file = os.path.abspath(zip_file)

        # Check if both files exist
        if os.path.isfile(abs_html_file) and os.path.isfile(abs_zip_file):
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
                "seq_processed", uploads_folder, "fastqc", bucket, region
            )
            multiqc.run(multiqc_folder, outdir=multiqc_folder)
            bucket_upload_directory = (
                region + "/MultiQC_report/" + uploads_folder
            )
            # upload the html file
            bucket_chunked_upload(
                local_file_path=multiqc_folder + "/multiqc_report.html",
                destination_upload_directory=bucket_upload_directory,
                destination_blob_name="multiqc_report.html",
                process_id=None,
                upload_type=None,
                bucket_name=bucket,
            )

            bucket_upload_directory = bucket_upload_directory + "/multiqc_data"
            # and upload the folder of the report contents
            bucket_upload_folder(
                folder_path=multiqc_folder + "/multiqc_data",
                destination_upload_directory=bucket_upload_directory,
                process_id=None,
                upload_type=None,
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
    bucket = process_data["project_id"]

    # Check if regions are specified
    if process_data["regions"]:
        # Iterate through each region
        for region in process_data["regions"]:
            # Construct the path to the multiqc folder
            multiqc_folder = os.path.join(
                "seq_processed", uploads_folder, "fastqc", bucket, region
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
