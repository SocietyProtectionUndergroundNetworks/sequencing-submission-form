import logging
from flask_app import celery_app
from redis import Redis
from redis.exceptions import LockError
from contextlib import contextmanager
from helpers.bucket import (
    bucket_chunked_upload_v2,
    bucket_upload_folder_v2,
    download_file_from_bucket,
)
from helpers.fastqc import (
    create_fastqc_report,
    create_multiqc_report,
)
from helpers.lotus2 import (
    generate_lotus2_report,
    generate_all_lotus2_reports,
)
from helpers.r_scripts import (
    generate_rscripts_report,
    generate_all_rscripts_reports,
)
from helpers.ecoregions import update_external_samples_with_ecoregions
from helpers.share_directory import sync_project
from helpers.hetzner_vm import send_vm_status_to_slack

logger = logging.getLogger("my_app_logger")

# Initialize Redis connection
redis_client = Redis(host="redis", port=6379, db=0)


@contextmanager
def redis_lock(lock_name, expire_time=86400):
    """
    Context manager for Redis-based locking.
    Attempts to acquire a lock with a unique name (lock_name).
    """
    acquired = redis_client.setnx(lock_name, "locked")

    if not acquired:
        # Log and raise an exception so execution stops
        logger.info(f"Task with lock {lock_name} is already running.")
        raise LockError(f"Lock already acquired: {lock_name}")

    try:
        redis_client.expire(lock_name, expire_time)  # Set expiration
        yield  # Task runs only if lock is acquired
    finally:
        redis_client.delete(lock_name)  # Ensure lock is released


@celery_app.task
def generate_lotus2_report_async(
    process_id, input_dir, amplicon_type, debug, analysis_type_id, parameters
):
    lock_key = (
        f"celery-lock:generate_lotus2_report:{process_id}:{analysis_type_id}"
    )

    try:
        with redis_lock(lock_key):
            generate_lotus2_report(
                process_id,
                input_dir,
                amplicon_type,
                debug,
                analysis_type_id,
                parameters,
            )

    except LockError:
        logger.info(
            f"Skipping execution: Task generate_lotus2_report_async "
            f"is already running for process_id:"
            f"{process_id} and analysis_type_id:{analysis_type_id}."
        )

    except Exception as e:
        logger.error(f"Unexpected error in generate_lotus2_report_async: {e}")
        raise


@celery_app.task
def generate_rscripts_report_async(
    process_id, input_dir, amplicon_type, analysis_type_id
):
    generate_rscripts_report(
        process_id, input_dir, amplicon_type, analysis_type_id
    )


@celery_app.task
def generate_all_rscripts_reports_async(amplicon_type, analysis_type_id):
    generate_all_rscripts_reports(amplicon_type, analysis_type_id)


@celery_app.task
def generate_all_lotus2_reports_async(analysis_type_id, from_id, to_id):
    lock_key = f"celery-lock:generate_all_lotus2_reports:{analysis_type_id}"
    try:
        with redis_lock(lock_key):
            generate_all_lotus2_reports(analysis_type_id, from_id, to_id)
    except LockError:
        logger.info(
            f"Skipping execution: Task is already "
            f"running for analysis_type_id {analysis_type_id}."
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in generate_all_lotus2_reports_async: {e}"
        )
        raise


@celery_app.task
def bucket_upload_folder_v2_async(
    folder_path, destination_upload_directory, bucket
):
    bucket_upload_folder_v2(folder_path, destination_upload_directory, bucket)


@celery_app.task
def create_fastqc_report_async(fastq_file, input_folder, bucket, region):
    create_fastqc_report(fastq_file, input_folder, bucket, region)


@celery_app.task
def bucket_chunked_upload_v2_async(
    local_file_path,
    destination_upload_directory,
    destination_blob_name,
    sequencer_file_id,
    bucket_name,
    known_md5,
):
    bucket_chunked_upload_v2(
        local_file_path,
        destination_upload_directory,
        destination_blob_name,
        sequencer_file_id,
        bucket_name,
        known_md5,
    )


@celery_app.task
def create_multiqc_report_async(process_id):
    create_multiqc_report(process_id)


@celery_app.task
def update_external_samples_with_ecoregions_async():
    update_external_samples_with_ecoregions()


@celery_app.task
def sync_project_async(process_id):
    lock_key = f"celery-lock:sync_project:{process_id}"
    logger.info("The lock key is" + lock_key)
    try:
        with redis_lock(lock_key):
            sync_project(process_id)

    except LockError:
        logger.info(
            f"Skipping execution: Task sync_project_async "
            f"is already running for process_id:"
            f"{process_id}"
        )

    except Exception as e:
        logger.error(f"Unexpected error in sync_project_async: {e}")
        raise


@celery_app.task
def download_file_from_bucket_async(bucket_name, blob_path, local_file_path):
    download_file_from_bucket(bucket_name, blob_path, local_file_path)


@celery_app.task(name="tasks.send_vm_status_to_slack_task")
def send_vm_status_to_slack_task():
    send_vm_status_to_slack()
