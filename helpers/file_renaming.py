# Script for renaming fastq files received from Scripps Research.  Requires a
# sample key with file name string matches and desired name changes to be
# specified in-script. Takes a directory containing the files to be changed
# as an argument.

import os
import json
import hashlib
import logging
from pathlib import Path
from models.upload import Upload
from helpers.csv import get_csv_data

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def generate_new_filename(current_filename, csv_sequence_dict):
    # Split the filename into parts
    parts = current_filename.split("_")
    # Try matching the longest possible prefix from the
    # parts with the dictionary keys
    for i in range(len(parts), 0, -1):
        prefix = "_".join(parts[:i])
        if prefix in csv_sequence_dict:
            sample_id = csv_sequence_dict[prefix]["sample_id"]
            # Replace 'RIBO' with 'SSU' in the sample_id if needed
            new_sample_id = (
                sample_id.replace("RIBO", "SSU")
                if "RIBO" in sample_id
                else sample_id
            )
            # Join the new sample_id with the remaining parts of the filename
            new_filename = "_".join([new_sample_id] + parts[i:])
            to_return = {}
            to_return["new_filename"] = new_filename
            to_return["bucket"] = csv_sequence_dict[prefix]["bucket"]
            to_return["region"] = csv_sequence_dict[prefix]["region"]
            to_return["sample_id"] = csv_sequence_dict[prefix]["sample_id"]
            return to_return

    # If no matching prefix is found, return None
    return None


def get_csv_sequence_dict(data):
    csv_sequence_dict = {}

    # Loop through the data dictionary and build the sequence dictionary
    for sample_id_safe, row in data.items():
        sequencer_id = row["sequencer_id"]
        sample_id = row["sample_id"]
        bucket = row["project"]
        region = row["region"]

        csv_sequence_dict[sequencer_id] = {
            "sample_id": sample_id,
            "bucket": bucket,
            "region": region,
        }

    return csv_sequence_dict


def get_all_files_new_names(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    csv_filepath = path / upload.csv_filename
    cvs_records = get_csv_data(csv_filepath)
    csv_sequence_dict = get_csv_sequence_dict(cvs_records)
    extract_directory = Path("processing", uploads_folder)

    # Get a list of all file names in the directory
    file_names = os.listdir(extract_directory)

    new_file_names = {}
    # Iterate through each file in the directory
    for file_name in file_names:
        # Generate the new file name
        new_file_names[file_name] = generate_new_filename(
            file_name, csv_sequence_dict
        )

    return csv_sequence_dict, new_file_names


def rename_files(csv_file_path, directory_path, files_json):
    matching_files_dict = json.loads(files_json)

    results = {}
    not_found = []

    cvs_records = get_csv_data(csv_file_path)
    csv_sequence_dict = get_csv_sequence_dict(cvs_records)

    # Get a list of all file names in the directory
    file_names = os.listdir(directory_path)

    # Iterate through each file in the directory
    for file_name in file_names:
        # Get the full path of the current file
        old_file_path = os.path.join(directory_path, file_name)

        # Generate the new file name
        new_file_name_data = generate_new_filename(
            file_name, csv_sequence_dict
        )

        if new_file_name_data:
            new_file_name = new_file_name_data["new_filename"]
            if new_file_name == file_name:
                results[file_name] = (
                    f"New and old names are the same for {new_file_name}"
                )
                matching_files_dict[file_name]["new_filename"] = new_file_name
                matching_files_dict[file_name]["bucket"] = new_file_name_data[
                    "bucket"
                ]
                matching_files_dict[file_name]["folder"] = new_file_name_data[
                    "region"
                ]
                matching_files_dict[file_name]["csv_sample_id"] = (
                    new_file_name_data["sample_id"]
                )
            elif new_file_name in file_names:
                # Check for duplicate names
                results[file_name] = (
                    f"Duplicate file name: {new_file_name}. Skipping renaming"
                )
            else:
                # Get the full path of the new file name
                new_file_path = os.path.join(directory_path, new_file_name)

                # Rename the file
                os.rename(old_file_path, new_file_path)
                results[file_name] = f"Renamed to {new_file_name}"

                matching_files_dict[file_name]["new_filename"] = new_file_name
                matching_files_dict[file_name]["bucket"] = new_file_name_data[
                    "bucket"
                ]
                matching_files_dict[file_name]["folder"] = new_file_name_data[
                    "region"
                ]
                matching_files_dict[file_name]["csv_sample_id"] = (
                    new_file_name_data["sample_id"]
                )
        else:
            not_found.append(file_name)

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

    if rename_results:
        Upload.mark_field_as_true(process_id, "files_renamed")
        return {
            "msg": "Files renamed successfully.",
            "results": rename_results,
            "not_found": not_found,
            "files_dict": files_dict,
        }
    return {"error": "Something went wrong while renaming files."}


def find_all_files_new_names(process_id):
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    csv_filepath = path / upload.csv_filename

    extract_directory = Path("processing", uploads_folder)
    rename_results, not_found, files_dict = rename_files(
        csv_filepath, extract_directory, upload.files_json
    )

    if rename_results:
        Upload.mark_field_as_true(process_id, "files_renamed")
        return {
            "msg": "Files renamed successfully.",
            "results": rename_results,
            "not_found": not_found,
            "files_dict": files_dict,
        }
    return {"error": "Something went wrong while renaming files."}
