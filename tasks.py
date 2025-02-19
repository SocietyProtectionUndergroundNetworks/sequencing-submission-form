import logging
from celery import current_app as celery_app
from redis import Redis
from redis.exceptions import LockError
from contextlib import contextmanager
from helpers.bucket import (
    download_bucket_contents,
    bucket_chunked_upload_v2,
    bucket_upload_folder_v2,
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

    if acquired:
        redis_client.expire(lock_name, expire_time)

    try:
        if acquired:
            yield  # Only run the task if the lock was acquired
        else:
            logger.info(f"Task with lock {lock_name} is already running.")
            # Ensure we always yield to avoid "generator didn't yield" error
            yield
    finally:
        if acquired:
            redis_client.delete(lock_name)


@celery_app.task
def generate_lotus2_report_async(
    process_id, input_dir, amplicon_type, debug, analysis_type_id, parameters
):
    lock_key = (
        f"celery-lock:generate_lotus2_report:{process_id}:{analysis_type_id}"
    )

    try:
        # Try to acquire the lock
        with redis_lock(lock_key):
            # If lock is acquired, proceed with the task
            generate_lotus2_report(
                process_id,
                input_dir,
                amplicon_type,
                debug,
                analysis_type_id,
                parameters,
            )

    except Exception:
        # If the task is already locked (running), log a
        # message instead of raising an error
        logger.info(
            f"Task generate_lotus2_report_async for process_id:{process_id} "
            f"and analysis_type_id:{analysis_type_id} is already running. "
            "Skipping execution."
        )


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
        # Try to acquire the lock
        with redis_lock(lock_key):
            # If lock is acquired, proceed with the task
            generate_all_lotus2_reports(analysis_type_id, from_id, to_id)
    except LockError:
        # If a lock error occurs, log a message indicating the task is locked
        logger.info(
            f"Task generate_all_lotus2_reports_async for "
            f"analysis_type_id:{analysis_type_id} "
            f"is already running. Skipping execution."
        )
    except Exception as e:
        # Handle other exceptions separately
        logger.error(
            f"An unexpected error occurred in "
            f"generate_all_lotus2_reports_async: {e}"
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
def download_bucket_contents_async(bucket):
    download_bucket_contents(bucket)


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
