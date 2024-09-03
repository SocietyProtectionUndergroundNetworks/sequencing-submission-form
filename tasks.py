from celery import current_app as celery_app
from helpers.bucket import (
    upload_raw_file_to_storage,
    upload_final_files_to_storage,
    download_bucket_contents,
    process_fastq_files,
    bucket_chunked_upload_v2,
)
from helpers.unzip import unzip_raw_file
from helpers.fastqc import (
    fastqc_multiqc_files,
    create_fastqc_report,
    create_multiqc_report,
)


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
