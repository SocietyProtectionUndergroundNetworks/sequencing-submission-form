from celery import current_app as celery_app
from redis import Redis
from contextlib import contextmanager
from helpers.bucket import (
    upload_raw_file_to_storage,
    upload_final_files_to_storage,
    download_bucket_contents,
    process_fastq_files,
    bucket_chunked_upload_v2,
    bucket_upload_folder_v2,
)
from helpers.unzip import unzip_raw_file
from helpers.fastqc import (
    fastqc_multiqc_files,
    create_fastqc_report,
    create_multiqc_report,
)
from helpers.lotus2 import generate_lotus2_report
from helpers.r_scripts import generate_rscripts_report

# Initialize Redis connection
redis_client = Redis(host="redis", port=6379, db=0)


@contextmanager
def redis_lock(lock_name, expire_time=86400):
    """
    Context manager for Redis-based locking.
    Attempts to acquire a lock with a unique name (lock_name).
    """
    # Try to acquire the lock
    if redis_client.setnx(lock_name, "locked"):
        # Set an expiration to prevent deadlock if something goes wrong
        redis_client.expire(lock_name, expire_time)
        try:
            yield  # Run the task within the lock
        finally:
            # Release the lock after task completion
            redis_client.delete(lock_name)
    else:
        # Log or handle that the lock is already acquired
        print(f"Task with lock {lock_name} is already running.")


@celery_app.task
def generate_lotus2_report_async(
    process_id, input_dir, amplicon_type, debug, analysis_type_id
):
    # Create a lock key combining process_id and
    # analysis_type_id for uniqueness
    lock_key = (
        f"celery-lock:generate_lotus2_report:{process_id}:{analysis_type_id}"
    )
    with redis_lock(lock_key):
        # This code only executes if the lock is acquired
        generate_lotus2_report(
            process_id, input_dir, amplicon_type, debug, analysis_type_id
        )


@celery_app.task
def generate_rscripts_report_async(
    region_nr, process_id, input_dir, amplicon_type, debug
):
    generate_rscripts_report(
        region_nr, process_id, input_dir, amplicon_type, debug
    )


@celery_app.task
def bucket_upload_folder_v2_async(
    folder_path, destination_upload_directory, bucket
):
    bucket_upload_folder_v2(folder_path, destination_upload_directory, bucket)


@celery_app.task
def upload_raw_file_to_storage_async(process_id, filename):
    upload_raw_file_to_storage(process_id, filename)


@celery_app.task
def process_fastq_files_async():
    process_fastq_files()


@celery_app.task
def unzip_raw_file_async(process_id, filename):
    unzip_raw_file(process_id, filename)


@celery_app.task
def fastqc_multiqc_files_async(process_id):
    fastqc_multiqc_files(process_id)


@celery_app.task
def create_fastqc_report_async(fastq_file, input_folder, bucket, region):
    create_fastqc_report(fastq_file, input_folder, bucket, region)


@celery_app.task
def upload_final_files_to_storage_async(process_id):
    upload_final_files_to_storage(process_id)


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
