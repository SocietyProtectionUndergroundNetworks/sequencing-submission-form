import os
import subprocess
import json
import multiqc
from celery import current_app as celery_app

@celery_app.task
def your_task_name():
    print('this was called via celery')
    pass

@celery_app.task    
def fastqc_multiqc_files_async(input_folder):
    print('Inside celery function fastqc_multiqc_files_async')
    print('input_folder is ' + str(input_folder))

    results=[]
    print('input_folder is ' + str(input_folder))
    output_folder = os.path.join(input_folder, 'fastqc')
    os.makedirs(output_folder, exist_ok=True)
    
    # Run fastqc on all raw fastq.gz files within the 'fastqc' conda environment
    fastq_files = [f for f in os.listdir(input_folder) if f.endswith('.fastq.gz')]
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
    
    results.append("Finished") 
    return results 
    