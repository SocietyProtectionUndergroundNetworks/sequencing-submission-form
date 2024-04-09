import os
import multiqc
import subprocess
import json
from pathlib import Path
from models.upload import Upload
from helpers.bucket import bucket_upload_folder
import logging
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

def get_multiqc_report(process_id, bucket, folder):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder


    extract_directory = upload.extract_directory

    fastqc_path = os.path.join(extract_directory, 'fastqc', bucket, folder)

    multiqc_report_exists = os.path.exists(os.path.join(fastqc_path, 'multiqc_report.html'))
    to_return = {
        'multiqc_report_exists': multiqc_report_exists,
        'multiqc_report_path': fastqc_path
    }

    return to_return

def get_fastqc_progress(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    files_dict_db = upload.get_files_json()

    count_fastq_gz = 0
    progress_text = ''
    process_finished = 0

    extract_directory = upload.extract_directory
    fastqc_process_id = upload.fastqc_process_id

    fastqc_path = os.path.join(extract_directory, 'fastqc')

    from tasks import fastqc_multiqc_files_async
    task = fastqc_multiqc_files_async.AsyncResult(fastqc_process_id)

    if not task.ready():
        # count the files we should have
        files_main = os.listdir(extract_directory)
        count_fastq_gz = sum(1 for file in files_main if ((file.endswith('.fastq.gz') or file.endswith('.fastq')) and not (file.startswith('._'))))

        # Get how many are done
        progress_text = upload.fastqc_files_progress
    else:
        process_finished = 1
        upload.mark_field_as_true(process_id, "fastqc_run")

    multiqc_report_exists = os.path.exists(os.path.join(fastqc_path, 'multiqc_report.html'))

    to_return = {
        'process_finished': process_finished,
        'files_main': count_fastq_gz,
        'progress_text': progress_text,
        'multiqc_report_exists': multiqc_report_exists,
        'multiqc_report_path': fastqc_path,
        'files_dict_db': files_dict_db
    }

    return to_return

def init_fastqc_multiqc_files(process_id):

    upload = Upload.get(process_id)
    from tasks import fastqc_multiqc_files_async
    try:
        result = fastqc_multiqc_files_async.delay(process_id)
        logger.info(f"Celery multiqc task called successfully! Task ID: {result.id}")
        task_id = result.id
        upload.update_fastqc_process_id(process_id, task_id)
    except Exception as e:
        logger.error("This is an error message from upload.py")
        logger.error(e)

def fastqc_multiqc_files(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    input_folder = str(upload.extract_directory)
    files_json = json.loads(upload.files_json)

    new_files_json = {
        data["new_filename"]: {
            "bucket": data.get("bucket"),
            "folder": data.get("folder"),
            "old_filename": key
        }
        for key, data in files_json.items()
        if "bucket" in data and "folder" in data
    }

    results=[]
    output_folder = os.path.join(input_folder, 'fastqc')
    os.makedirs(output_folder, exist_ok=True)
    output_folders = {}
    nr_output_folders = 0
    files_done = 0
    # Run fastqc on all raw fastq.gz files within the 'fastqc' conda environment
    fastq_files = [f for f in os.listdir(input_folder) if ((f.endswith('.fastq.gz') or f.endswith('.fastq')) and not f.startswith('.'))]
    nr_files = len(fastq_files)
    for fastq_file in fastq_files:
        # check that the file exists in our files_json
        if (fastq_file in new_files_json):
            bucket = new_files_json[fastq_file]["bucket"]
            folder = new_files_json[fastq_file]["folder"]

            if (bucket not in output_folders):
                output_folders[bucket] = {}

            if (folder not in output_folders[bucket]):
                output_folders[bucket][folder] = True
                nr_output_folders += 1

            print('file we will try is ' + str(fastq_file))

            output_folder_of_file = os.path.join(output_folder, bucket, folder)
            Path(output_folder_of_file).mkdir(parents=True, exist_ok=True)
            input_file = os.path.join(input_folder, fastq_file)
            output_file = os.path.join(output_folder_of_file, fastq_file.replace('.fastq.gz', '_fastqc.zip'))
            fastqc_cmd = f'/usr/local/bin/FastQC/fastqc -o {output_folder_of_file} {input_file}'
            subprocess.run(fastqc_cmd, shell=True, executable='/bin/bash')
            files_done += 1
            progress = str(files_done) + ' fastq files done out of ' + str(nr_files)
            if (nr_files == files_done):
                progress = progress + '. Starting creation of multiqc reports'
            Upload.update_fastqc_files_progress(process_id, progress)

    # Run the multiqc process differently for each project.
    multiqc_done =0
    for bucket, folders in output_folders.items():
        for folder in folders:
            multiqc_folder = os.path.join(output_folder, bucket, folder)
            multiqc.run(multiqc_folder, outdir=multiqc_folder)
            fastq_files_to_delete = [f for f in os.listdir(multiqc_folder) if f.endswith('_fastqc.html') or f.endswith('_fastqc.zip')]
            for file_to_delete in fastq_files_to_delete:
                path_to_delete = os.path.join(multiqc_folder, file_to_delete)
                os.remove(path_to_delete)

            # upload the multiqc files to the project bucket
            bucket_upload_folder(multiqc_folder, folder+'/MultiQC_report'+uploads_folder, process_id, 'fastqc_files', bucket)

            multiqc_done = multiqc_done + 1
            progress = str(multiqc_done) + ' multiqc reports done out of ' + str(nr_output_folders)
            Upload.update_fastqc_files_progress(process_id, progress)

    fastqc_path = os.path.join(input_folder , 'fastqc')
    Upload.mark_field_as_true(process_id, 'fastqc_sent_to_bucket')

    results.append("Finished")
    return results
