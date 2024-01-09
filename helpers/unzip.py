from models.upload import Upload
from pathlib import Path
import gzip
import tarfile
import os

# for debug reasons only
import time 

def unzip_raw_file(process_id):
    # in order to continue on the same process, lets get the id from the form

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    filename = upload.gz_filename
    save_path = path / filename

    extract_directory = Path("processing", uploads_folder)
    gunzip_result = extract_uploaded_gzip(process_id, save_path, extract_directory)

    if (gunzip_result):
        Upload.mark_field_as_true(process_id, 'gz_unziped')
        Upload.update_gz_unziped_progress(process_id, 100)

        # count the files ending with fastq.gz
        file_names = os.listdir(extract_directory)
        matching_files = [filename for filename in file_names if filename.endswith('.fastq.gz')]
        nr_files = 0
        if (matching_files):
            nr_files=len(matching_files)
            # Convert the list to a dictionary with empty parameters
            matching_files_dict = {filename: {'new_filename': '', 'fastqc': ''} for filename in matching_files}
            Upload.update_files_json(process_id, matching_files_dict)    

def extract_tar_without_structure(process_id, tar_file, extract_path):
    total_size = os.path.getsize(tar_file)
    current_size = 0

    with tarfile.open(tar_file, 'r') as tar:
        for member in tar.getmembers():
            member.name = os.path.basename(member.name)
            tar.extract(member, path=extract_path)
            current_size += member.size
            track_progress(process_id, current_size, total_size)
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
                    track_progress(process_id, current_size, total_size)

        if file_name.endswith('.tar'):
            extract_tar_without_structure(process_id, extract_path, extract_directory)
            os.remove(extract_path)
            
    return True
    
def track_progress(process_id, current_size, total_size):
    if total_size > 0:
        progress_percentage = (current_size / total_size) * 100
        Upload.update_gz_unziped_progress(process_id, round(progress_percentage))
        print(f"Progress: {progress_percentage:.2f}%")

def get_progress_db_unzip(process_id):
    upload = Upload.get(process_id)
    progress = upload.gz_unziped_progress if upload.gz_unziped_progress not in [None] else 0
    return progress