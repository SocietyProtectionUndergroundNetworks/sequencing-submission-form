# Script for renaming fastq files received from Scripps Research.  Requires a sample key with file name string matches and desired name changes to be specified in-script. Takes a directory containing the files to be changed as an argument.

import os
import csv
import subprocess
import json
import multiqc
import hashlib
import logging
from pathlib import Path
from flask import current_app as app  # Import the 'app' instance
from models.upload import Upload

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def rename_files(csv_file_path, directory_path, files_json):
    matching_files_dict = json.loads(files_json)

    results = {}
    not_found = []

    # Open the CSV file using csv.reader
    with open(
        csv_file_path, "r", newline="", encoding="utf-8-sig"
    ) as csv_file:
        csv_reader = csv.reader(csv_file)
        # Assuming the first row contains headers
        headers = next(csv_reader)

        # Find the indices of the required columns
        sequencer_id_index = headers.index("Sequencer_ID")
        sample_id_index = headers.index("Sample_ID")
        bucket_index = headers.index("Project")
        bucket_folder_index = headers.index("Region")

        # Get a list of all file names in the directory
        file_names = os.listdir(directory_path)

        # Iterate through each row in the CSV file
        for row in csv_reader:
            sampleid = str(row[sequencer_id_index])
            name = str(row[sample_id_index])
            bucket = str(row[bucket_index])
            bucket_folder = str(row[bucket_folder_index])

            # Find the matching filenames based on the Sequencer_ID
            matching_files = [
                filename
                for filename in file_names
                if filename.startswith(sampleid.split("_S", 1)[0] + "_S")
            ]
            for matching_file in matching_files:
                # Get the full path of the matching file
                old_file_path = os.path.join(directory_path, matching_file)

                # Extract the portion after '_S' from the matching file
                extension = matching_file.split("_S")[-1]

                # Replace 'RIBO' with 'SSU' in the 'Name' column
                if "RIBO" in name:
                    new_name = name.replace("RIBO", "SSU")
                else:
                    new_name = name

                # Create the new file name based on the extracted extension, modified 'Name' column, and the 'CCBB' prefix
                new_file_name = new_name + "_S" + extension

                if new_file_name == matching_file:
                    results[matching_file] = (
                        f"New and old names the same for {new_file_name}"
                    )
                    matching_files_dict[matching_file][
                        "new_filename"
                    ] = new_file_name
                    matching_files_dict[matching_file]["bucket"] = bucket
                    matching_files_dict[matching_file][
                        "folder"
                    ] = bucket_folder
                    matching_files_dict[matching_file]["csv_sample_id"] = name
                elif new_file_name in file_names:
                    # Check for duplicate names
                    results[matching_file] = (
                        f"Duplicate file name: {new_file_name}. Skipping renaming"
                    )
                else:
                    # Get the full path of the new file name
                    new_file_path = os.path.join(directory_path, new_file_name)

                    # Rename the file
                    os.rename(old_file_path, new_file_path)
                    # results.append(f"Renamed {matching_file} to {new_file_name}")
                    results[matching_file] = f"Renamed to {new_file_name}"

                    matching_files_dict[matching_file][
                        "new_filename"
                    ] = new_file_name
                    matching_files_dict[matching_file]["bucket"] = bucket
                    matching_files_dict[matching_file][
                        "folder"
                    ] = bucket_folder
                    matching_files_dict[matching_file]["csv_sample_id"] = name

            if not matching_files:
                not_found.append(sampleid)
    return results, not_found, matching_files_dict


def calculate_md5(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def rename_all_files(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    csv_filepath = path / upload.csv_filename

    extract_directory = Path("processing", uploads_folder)
    rename_results, not_found, files_dict = rename_files(
        csv_filepath, extract_directory, upload.files_json
    )
    Upload.update_files_json(process_id, files_dict)

    to_render = "<br>".join(rename_results)

    if rename_results:
        Upload.mark_field_as_true(process_id, "files_renamed")
        return {
            "msg": "Files renamed successfully.",
            "results": rename_results,
            "not_found": not_found,
            "files_dict": files_dict,
        }
    return {"error": "Something went wrong while renaming files."}
