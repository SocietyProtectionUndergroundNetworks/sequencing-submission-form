import os
from models.upload import Upload


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
        'multiqc_report_exists': multiqc_report_exists
    }

    return to_return