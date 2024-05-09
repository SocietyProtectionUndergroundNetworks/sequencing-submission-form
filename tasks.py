from celery import current_app as celery_app
from helpers.bucket import upload_raw_file_to_storage, upload_final_files_to_storage, download_bucket_contents
from helpers.unzip import unzip_raw_file
from helpers.fastqc import fastqc_multiqc_files
from helpers.discord import send_message

@celery_app.task
def upload_raw_file_to_storage_async(process_id, filename):
    upload_raw_file_to_storage(process_id, filename)

@celery_app.task
def unzip_raw_file_async(process_id, filename):
    unzip_raw_file(process_id, filename)

@celery_app.task    
def fastqc_multiqc_files_async(process_id):
    fastqc_multiqc_files(process_id)
    
@celery_app.task
def upload_final_files_to_storage_async(process_id):
    upload_final_files_to_storage(process_id)
    
@celery_app.task
def download_bucket_contents_async(bucket):
    download_bucket_contents(bucket)      
    
@celery_app.task
def send_message_async(message):
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_message(message))   