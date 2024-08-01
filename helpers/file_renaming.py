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
    # List of separators to try
    separators = ["_", "-"]
    # logger.info('The current_filename is '+ str(current_filename))

    # Remove the .fastq.gz extension to get the base name
    if current_filename.endswith(".fastq.gz"):
        base_filename = current_filename[
            :-9
        ]  # Removing '.fastq.gz' (9 characters)
    else:
        base_filename = current_filename.rsplit(".", 1)[0]
    # logger.info('The base_filename is '+ str(current_filename))

    # logger.info('the sequence_dict is ')
    # logger.info(csv_sequence_dict)

    # Check if the base filename matches any key in the csv_sequence_dict
    if base_filename in csv_sequence_dict:
        sample_id = csv_sequence_dict[base_filename]["sample_id"]
        new_sample_id = (
            sample_id.replace("RIBO", "SSU")
            if "RIBO" in sample_id
            else sample_id
        )

        name_base = current_filename[len(base_filename) :]  # noqa: E203
        new_filename = new_sample_id + name_base
        return {
            "new_filename": new_filename,
            "bucket": csv_sequence_dict[base_filename]["bucket"],
            "region": csv_sequence_dict[base_filename]["region"],
            "sample_id": csv_sequence_dict[base_filename]["sample_id"],
        }

    # If no exact base filename match, try matching using each separator
    for separator in separators:
        # Split the base filename into parts
        parts = base_filename.split(separator)

        # Iterate over the parts to find a matching prefix in the dictionary
        for i in range(len(parts), 0, -1):
            prefix = separator.join(parts[:i])
            # Ensure that the prefix is a complete match and not a partial one
            if prefix in csv_sequence_dict:
                sample_id = csv_sequence_dict[prefix]["sample_id"]
                # Ensure exact matching for sequence ID
                if not base_filename.startswith(sample_id):
                    continue

                new_sample_id = (
                    sample_id.replace("RIBO", "SSU")
                    if "RIBO" in sample_id
                    else sample_id
                )
                n_base = current_filename[len(base_filename) :]  # noqa: E203
                new_filename = (
                    separator.join([new_sample_id] + parts[i:]) + n_base
                )
                return {
                    "new_filename": new_filename,
                    "bucket": csv_sequence_dict[prefix]["bucket"],
                    "region": csv_sequence_dict[prefix]["region"],
                    "sample_id": csv_sequence_dict[prefix]["sample_id"],
                }

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
