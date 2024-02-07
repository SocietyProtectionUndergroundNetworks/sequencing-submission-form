from celery import current_app as celery_app
from helpers.bucket import upload_raw_file_to_storage, upload_renamed_files_to_storage
from helpers.unzip import unzip_raw_file
from helpers.fastqc import fastqc_multiqc_files

@celery_app.task
def upload_raw_file_to_storage_async(process_id, filename):
    upload_raw_file_to_storage(process_id, filename)

@celery_app.task
def unzip_raw_file_async(process_id):
    unzip_raw_file(process_id)

@celery_app.task    
def fastqc_multiqc_files_async(process_id):
    fastqc_multiqc_files(process_id)
    
@celery_app.task
def upload_renamed_files_to_storage_async(process_id):
    upload_renamed_files_to_storage(process_id)  
    
    