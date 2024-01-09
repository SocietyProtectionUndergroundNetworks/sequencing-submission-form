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
    
    chunk_nr_mb = os.environ.get('GOOGLE_STORAGE_CHUNK_SIZE_MB', 20)
    
    chunk_size = chunk_nr_mb * 1024 * 1024  # 20 MB chunk size

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(f'uploads/{destination_upload_directory}/{destination_blob_name}')


    total_size = os.path.getsize(local_file_path)
    uploaded_bytes = 0

    with open(local_file_path, 'rb') as file:
        blob.chunk_size = chunk_size
        chunk_num = 0
        chunks = []

        while True:
            data = file.read(chunk_size)
            if not data:
                break

            temp_blob = bucket.blob(f'uploads/{destination_upload_directory}/{destination_blob_name}.part{chunk_num}')
            temp_blob.upload_from_string(data, content_type='application/octet-stream')
            chunks.append(temp_blob)
            chunk_num += 1

            uploaded_bytes += len(data)
            percentage = (uploaded_bytes / total_size) * 100
            update_progress_db(process_id, upload_type, percentage)
            print(f"Bytes uploaded: {uploaded_bytes} / {total_size} ({percentage:.2f}%)", flush=True)

        blob.compose(chunks)

        for temp_blob in chunks:
            temp_blob.delete()

        update_progress_db(process_id, upload_type, 100)
        return True
        #print(f"File {local_file_path} uploaded to {destination_blob_name} in {bucket_name} bucket.", flush=True)

def bucket_upload_folder(folder_path, destination_upload_directory, process_id, upload_type):
    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            destination_blob_name = os.path.relpath(file_path, folder_path)
            bucket_chunked_upload(file_path, destination_upload_directory, destination_blob_name, process_id, upload_type)
