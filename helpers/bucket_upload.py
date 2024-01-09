import os
import json

# Library about google cloud storage
from google.cloud import storage
from pathlib import Path
from models.upload import Upload

def upload_raw_file_to_storage(process_id):
    #app.logger.info('raw to storage starts')

    # in order to continue on the same process, lets get the id from the form
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    filename = upload.gz_filename
    save_path = path / filename
    raw_uploaded = bucket_chunked_upload(save_path, uploads_folder, filename, process_id, 'gz_raw')
    #Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')
    if (raw_uploaded):
        Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')

def update_progress_db(process_id, upload_type, percentage):
    if (upload_type=='gz_raw'):
        Upload.update_gz_sent_to_bucket_progress(process_id, round(percentage))

def get_progress_db(process_id, upload_type):
    progress = 0
    if (upload_type=='gz_raw'):
        upload = Upload.get(process_id)
        progress = upload.gz_sent_to_bucket_progress if upload.gz_sent_to_bucket_progress not in [None] else 0
    return progress
    
def bucket_chunked_upload(local_file_path, destination_upload_directory, destination_blob_name, process_id, upload_type):
    # Configure Google Cloud Storage
    bucket_name = os.environ.get('GOOGLE_STORAGE_BUCKET_NAME')
    project_id = os.environ.get('GOOGLE_STORAGE_PROJECT_ID')
    bucket_location = os.environ.get('GOOGLE_STORAGE_BUCKET_LOCATION')

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    total_size = os.path.getsize(local_file_path)

    # If the file is smaller than 30 MB, upload it directly
    if total_size <= 30 * 1024 * 1024:
        blob = bucket.blob(f'uploads/{destination_upload_directory}/{destination_blob_name}')
        blob.upload_from_filename(local_file_path)
        update_progress_db(process_id, upload_type, 100)
        return True

    # If the file is between 30 MB and 700 MB, do chunks of 30 MB each
    if 30 * 1024 * 1024 < total_size <= 700 * 1024 * 1024:
        chunk_size = 30 * 1024 * 1024

    # If the file is larger than 700 MB, separate it into 32 chunks
    else:
        chunk_size = total_size // 32

    chunk_num = 0
    chunks = []

    with open(local_file_path, 'rb') as file:
        while True:
            data = file.read(chunk_size)
            if not data:
                break

            temp_blob = bucket.blob(f'uploads/{destination_upload_directory}/{destination_blob_name}.part{chunk_num}')
            temp_blob.upload_from_string(data, content_type='application/octet-stream')
            chunks.append(temp_blob)
            chunk_num += 1

            update_progress_db(process_id, upload_type, (file.tell() / total_size) * 100)
            print(f"Bytes uploaded: {file.tell()} / {total_size}", flush=True)

        blob = bucket.blob(f'uploads/{destination_upload_directory}/{destination_blob_name}')
        blob.compose(chunks)

        for temp_blob in chunks:
            temp_blob.delete()

        update_progress_db(process_id, upload_type, 100)
        return True

def bucket_upload_folder(folder_path, destination_upload_directory, process_id, upload_type):
    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            destination_blob_name = os.path.relpath(file_path, folder_path)
            bucket_chunked_upload(file_path, destination_upload_directory, destination_blob_name, process_id, upload_type)
