import os
import json

# Library about google cloud storage
from google.cloud import storage


def update_progress(file_uuid, percentage):
    try:
        with open("upload_progress.json", "r") as file:
            progress_data = json.load(file)
    except FileNotFoundError:
        progress_data = {}

    progress_data[file_uuid] = percentage

    with open("upload_progress.json", "w") as file:
        json.dump(progress_data, file)

def get_progress(file_uuid):
    try:
        with open("upload_progress.json", "r") as file:
            progress_data = json.load(file)
            return progress_data.get(file_uuid, 0)
    except FileNotFoundError:
        return 0  
    
def chunked_upload(local_file_path, destination_blob_name, file_uuid):
    # Configure Google Cloud Storage
    bucket_name = os.environ.get('GOOGLE_STORAGE_BUCKET_NAME')
    project_id = os.environ.get('GOOGLE_STORAGE_PROJECT_ID')
    bucket_location = os.environ.get('GOOGLE_STORAGE_BUCKET_LOCATION')
    
    chunk_size = 20 * 1024 * 1024  # 20 MB chunk size

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(f'uploads/{destination_blob_name}')

    temp_directory = f"temp_{file_uuid}"

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

            temp_blob = bucket.blob(f'uploads/{temp_directory}/{destination_blob_name}.part{chunk_num}')
            temp_blob.upload_from_string(data, content_type='application/octet-stream')
            chunks.append(temp_blob)
            chunk_num += 1

            uploaded_bytes += len(data)
            percentage = (uploaded_bytes / total_size) * 100
            update_progress(file_uuid, percentage)
            print(f"Bytes uploaded: {uploaded_bytes} / {total_size} ({percentage:.2f}%)", flush=True)

        blob.compose(chunks)

        for temp_blob in chunks:
            temp_blob.delete()

        update_progress(file_uuid, 100)
        print(f"File {local_file_path} uploaded to {destination_blob_name} in {bucket_name} bucket.", flush=True)
        