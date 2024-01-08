# Script for renaming fastq files received from Scripps Research.  Requires a sample key with file name string matches and desired name changes to be specified in-script. Takes a directory containing the files to be changed as an argument. 

import os
import gzip
import csv
import tarfile
import pandas as pd
import subprocess
import json
import multiqc
import hashlib
from flask import current_app as app  # Import the 'app' instance

def extract_tar(tar_file, extract_path):
    with tarfile.open(tar_file, 'r') as tar:
        tar.extractall(path=extract_path)

def extract_tar_without_structure(tar_file, extract_path):
    with tarfile.open(tar_file, 'r') as tar:
        for member in tar.getmembers():
            member.name = os.path.basename(member.name)
            tar.extract(member, path=extract_path)

def extract_uploaded_gzip(uploaded_file_path, extract_directory):

    # Create the directory if it doesn't exist
    os.makedirs(extract_directory, exist_ok=True)

    # Get the file name from the full path
    uploaded_file_name = os.path.basename(uploaded_file_path)

    # Check if the uploaded file name ends with '.tar'
    if uploaded_file_name.endswith('.tar'):
        extract_tar_without_structure(uploaded_file_path, extract_directory)
        #os.remove(uploaded_file_name)
    else:
        # Check if the uploaded file name ends with '.gz'
        if not uploaded_file_name.endswith('.gz'):
            raise ValueError("The uploaded file is not a gzip file.")

        # Get the file name without the '.gz' extension
        file_name = os.path.splitext(uploaded_file_name)[0]

        # Path to extract the file to
        extract_path = os.path.join(extract_directory, file_name)

        # Extract the gzip file
        with gzip.open(uploaded_file_path, 'rb') as f_in:
            with open(extract_path, 'wb') as f_out:
                f_out.write(f_in.read())

        # check if the file is a tar, in which case we have more to do
        if file_name.endswith('.tar'):
            extract_tar_without_structure(extract_path, extract_directory)
            os.remove(extract_path)
    
    return True

def rename_files(csv_file_path, directory_path, files_json):
    matching_files_dict = json.loads(files_json)
    # Load the Excel file
    df = pd.read_csv(csv_file_path)
    
    results={}
    not_found=[]

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        sampleid = str(row['Sequencer_ID'])
        name = str(row['Sample_ID'])
        #app.logger.info('---')
        #app.logger.info('sampleid is ' + sampleid)
        #app.logger.info('name is ' + name)

        # Get a list of all file names in the directory
        file_names = os.listdir(directory_path)

        # Find the matching filenames based on the Sequencer_ID
        matching_files = [filename for filename in file_names if filename.startswith(sampleid.split('id', 1)[0] + 'id')]

        for matching_file in matching_files:
            # Get the full path of the matching file
            old_file_path = os.path.join(directory_path, matching_file)
            # app.logger.info('old_file_path is ' + old_file_path)

            # Extract the portion after '_S' from the matching file
            extension = matching_file.split('_S')[-1]

            # Replace 'RIBO' with 'SSU' in the 'Name' column
            if 'RIBO' in name:
                new_name = name.replace('RIBO', 'SSU')
            else:
                new_name = name
                
            # app.logger.info('new_name is ' + new_name)    

            # Create the new file name based on the extracted extension, modified 'Name' column, and the 'CCBB' prefix
            new_file_name = new_name + '_S' + extension
            # app.logger.info('new_file_name is ' + new_file_name)    

            # Check for duplicate names
            if new_file_name in file_names:
                # app.logger.info(f"Duplicate file name: {new_file_name}. Skipping renaming for {matching_file}")
                results[matching_file] = f"Duplicate file name: {new_file_name}. Skipping renaming"
                #results.append(f"Duplicate file name: {new_file_name}. Skipping renaming for {matching_file}")
            else:
                # Get the full path of the new file name
                new_file_path = os.path.join(directory_path, new_file_name)

                # Rename the file
                os.rename(old_file_path, new_file_path)
                #results.append(f"Renamed {matching_file} to {new_file_name}")
                results[matching_file] = f"Renamed to {new_file_name}"
                matching_files_dict[matching_file]['new_filename'] = new_file_name

        if not matching_files:
            not_found.append(sampleid)
            
    return results, not_found, matching_files_dict

def calculate_md5(file_path):
    md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            md5.update(chunk)
    return md5.hexdigest()
