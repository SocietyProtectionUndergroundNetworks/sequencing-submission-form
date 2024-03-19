from models.upload import Upload
from pathlib import Path
import gzip
import json
import tarfile
import os
import logging

logger = logging.getLogger("my_app_logger")

# for debug reasons only
import time 

def unzip_raw_file(process_id, filename):
    # in order to continue on the same process, lets get the id from the form

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    save_path = path / filename

    extract_directory = Path("processing", uploads_folder)
    gunzip_result = extract_uploaded_gzip(process_id, save_path, extract_directory)

    if (gunzip_result):
        # Upload.mark_field_as_true(process_id, 'gz_unziped')
        Upload.update_gz_unziped_progress(process_id, 100, filename)  

def extract_tar_without_structure(process_id, tar_file, extract_path):
    total_size = os.path.getsize(tar_file)
    current_size = 0
    filename = os.path.basename(tar_file)
    logger.info(filename)

    with tarfile.open(tar_file, 'r') as tar:
        for member in tar.getmembers():
            member.name = os.path.basename(member.name)
            tar.extract(member, path=extract_path)
            current_size += member.size
            track_progress(process_id, current_size, total_size, filename)
            # time.sleep(0.5)

def extract_tar(tar_file, extract_path):
    with tarfile.open(tar_file, 'r') as tar:
        tar.extractall(path=extract_path)

def extract_uploaded_gzip(process_id, uploaded_file_path, extract_directory):
    os.makedirs(extract_directory, exist_ok=True)
    uploaded_file_name = os.path.basename(uploaded_file_path)

    if uploaded_file_name.endswith('.tar'):
        extract_tar_without_structure(process_id, uploaded_file_path, extract_directory)
    else:
        if not uploaded_file_name.endswith('.gz'):
            raise ValueError("The uploaded file is not a gzip file.")

        file_name = os.path.splitext(uploaded_file_name)[0]
        extract_path = os.path.join(extract_directory, file_name)

        with gzip.open(uploaded_file_path, 'rb') as f_in:
            with open(extract_path, 'wb') as f_out:
                chunk_size = 100 * 1024 * 1024  # 100 MB chunk size
                total_size = os.path.getsize(uploaded_file_path)
                current_size = 0

                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    current_size += len(chunk)
                    f_out.write(chunk)
                    track_progress(process_id, current_size, total_size, file_name)

        if file_name.endswith('.tar'):
            extract_tar_without_structure(process_id, extract_path, extract_directory)
            os.remove(extract_path)
            
    return True
    
def track_progress(process_id, current_size, total_size, filename):
    if total_size > 0:
        progress_percentage = (current_size / total_size) * 100
        Upload.update_gz_unziped_progress(process_id, round(progress_percentage), filename)
        print(f"Progress: {progress_percentage:.2f}%")

def get_progress_db_unzip(process_id, file_id):
    upload = Upload.get(process_id)
    progress = 0
    gz_filedata = json.loads(upload.gz_filedata)
    for filename, file_data in gz_filedata.items():
        if 'form_fileidentifier' in file_data:
            if (file_data['form_fileidentifier'] == file_id):
                if ('gz_unziped_progress' in file_data):
                    progress = file_data['gz_unziped_progress']
    return progress
    
def unzip_raw(process_id, filename):

    from tasks import unzip_raw_file_async
    try:
        result = unzip_raw_file_async.delay(process_id, filename)
        logger.info(f"Celery unzip_raw_file_async task called successfully! Task ID: {result.id}")
        task_id = result.id
    except Exception as e:
        logger.error("This is an error message from upload.py while trying to unzip_raw_file_async")
        logger.error(e)

    return {"msg": "Process initiated"} 