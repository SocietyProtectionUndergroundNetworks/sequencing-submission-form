import os
import multiqc
import subprocess
from models.upload import Upload
from helpers.bucket import bucket_upload_folder


def get_fastqc_progress(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder

    count_fastq_gz = 0
    count_fastqc_html = 0
    process_finished = 0

    extract_directory = upload.extract_directory
    fastqc_process_id = upload.fastqc_process_id

    fastqc_path = os.path.join(extract_directory, 'fastqc')

    from tasks import fastqc_multiqc_files_async
    task = fastqc_multiqc_files_async.AsyncResult(fastqc_process_id)

    if not task.ready():
        # count the files we should have
        files_main = os.listdir(extract_directory)
        count_fastq_gz = sum(1 for file in files_main if file.endswith('.fastq.gz'))

        # Navigate to the "fastqc" subdirectory

        if os.path.exists(fastqc_path) and os.path.isdir(fastqc_path):
            # List all files in the "fastqc" subdirectory
            files_fastqc = os.listdir(fastqc_path)

            # Count the files that end with ".fastq.html" in the "fastqc" subdirectory
            count_fastqc_html = sum(1 for file in files_fastqc if file.endswith('fastqc.html'))
        else:
            count_fastqc_html = 0
    else:
        process_finished = 1
        upload.mark_field_as_true(process_id, "fastqc_run")

    multiqc_report_exists = os.path.exists(os.path.join(fastqc_path, 'multiqc_report.html'))

    to_return = {
        'process_finished': process_finished,
        'files_main': count_fastq_gz,
        'files_done': count_fastqc_html,
        'multiqc_report_exists': multiqc_report_exists,
        'multiqc_report_path': fastqc_path
    }

    return to_return
    
def fastqc_multiqc_files(input_folder, process_id):
    parent_folder = os.path.split(input_folder)

    uploads_folder = parent_folder[1]

    results=[]
    output_folder = os.path.join(input_folder, 'fastqc')
    os.makedirs(output_folder, exist_ok=True)
    
    # Run fastqc on all raw fastq.gz files within the 'fastqc' conda environment
    fastq_files = [f for f in os.listdir(input_folder) if f.endswith('.fastq.gz') and not f.startswith('.')]
    for fastq_file in fastq_files:
        print('file we will try is ' + str(fastq_file))
        input_file = os.path.join(input_folder, fastq_file)
        output_file = os.path.join(output_folder, fastq_file.replace('.fastq.gz', '_fastqc.zip'))
        fastqc_cmd = f'/usr/local/bin/FastQC/fastqc -o {output_folder} {input_file}'
        subprocess.run(fastqc_cmd, shell=True, executable='/bin/bash')
    
    multiqc.run(output_folder, outdir=output_folder)

    # Delete individual fastqc.html files and fastq.zip files
    for fastq_file in fastq_files:
        individual_fastqc_file = os.path.join(output_folder, fastq_file.replace('.fastq.gz', '_fastqc.html'))
        if not os.path.basename(individual_fastqc_file).startswith('.') and os.path.exists(individual_fastqc_file):
            os.remove(individual_fastqc_file)
        zip_file = os.path.join(output_folder, fastq_file.replace('.fastq.gz', '_fastqc.zip'))
        if not os.path.basename(zip_file).startswith('.') and os.path.exists(zip_file):
            os.remove(zip_file)
    
    fastqc_path = os.path.join(input_folder , 'fastqc')
    bucket_upload_folder(fastqc_path, 'uploads/'+uploads_folder, process_id, 'fastqc_files')
    Upload.mark_field_as_true(process_id, 'fastqc_sent_to_bucket')
    
    results.append("Finished") 
    return results     