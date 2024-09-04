import csv
import re
import os
import json
from helpers.bucket import list_buckets
import logging

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def make_safe_html_id(string, existing_ids=[]):
    # Remove any characters that are not allowed in HTML id attributes
    safe_string = re.sub(r"[^\w\s-]", "", string)

    # Replace spaces with underscores
    safe_string = safe_string.replace(" ", "_")

    # Ensure the string is unique and does not conflict with existing ids
    count = 1
    new_id = safe_string
    while new_id in existing_ids:
        new_id = f"{safe_string}_{count}"
        count += 1

    # Convert the string to lowercase
    safe_html_id = new_id.lower()

    return safe_html_id


def get_csv_columns(file_path):
    with open(file_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        csv_reader = csv.reader(csvfile)
        first_row = next(csv_reader)  # Get the first row (column names)

        # Strip whitespace from all column names in the first row
        trimmed_columns = [col.strip() for col in first_row]

    return trimmed_columns


def get_csv_data(file_path):
    data = {}
    existing_ids = []
    with open(file_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            # Strip whitespace from all values in the row
            trimmed_row = {
                key.strip(): value.strip() for key, value in row.items()
            }

            sample_id_safe = make_safe_html_id(
                trimmed_row["Sample_ID"]
                + "__"
                + trimmed_row["Sequencer_ID"]
                + "__"
                + trimmed_row["Project"],
                existing_ids,
            )
            existing_ids.append(sample_id_safe)
            data[sample_id_safe] = {
                "sample_id": trimmed_row["Sample_ID"],
                "sequencer_id": trimmed_row["Sequencer_ID"],
                "sequencer_provider": trimmed_row["Sequencing_provider"],
                "project": trimmed_row["Project"],
                "region": trimmed_row["Region"],
                "index_1": trimmed_row["Index_1"],
                "index_2": trimmed_row["Index_2"],
                "sample_id_safe": sample_id_safe,
            }
    return data


def validate_csv_column_names(column_names):
    expected_column_names = [
        "Sample_ID",
        "Sequencer_ID",
        "Sequencing_provider",
        "Project",
        "Region",
        "Index_1",
        "Index_2",
    ]

    # Compare column names and return a list of mismatched columns
    mismatched_columns = [
        col for col in column_names if col not in expected_column_names
    ]

    if mismatched_columns:
        mismatched_columns_text = ", ".join(mismatched_columns)
        return (
            f"The following columns do not have expected names: "
            f"{mismatched_columns_text}"
        )

    return True


def validate_csv_buckets(data, column_names):
    # Get bucket information
    bucket_info = list_buckets()

    expected_regions = [
        "ITS2",
        "ITS1",
        "SSU",
        "LSU",
        "Other",
        "Full_rDNA",
        "Full_ITS",
    ]

    # To store CSV values that do not exist as buckets
    not_found = []
    wrong_regions = []

    for sample_id_safe, row in data.items():
        csv_bucket_value = row["project"]
        csv_region_value = row["region"]

        # Check if the CSV value exists as a key in the bucket_info dictionary
        if csv_bucket_value.lower() not in bucket_info:
            not_found.append(csv_bucket_value)

        if csv_region_value not in expected_regions:
            wrong_regions.append(csv_region_value)

    # Deduplicate the lists
    not_found = list(set(not_found))
    wrong_regions = list(set(wrong_regions))

    if not_found:
        not_found_text = ", ".join(not_found)
        return (
            f"The following projects do not correspond to buckets: "
            f"--{not_found_text}--"
        )

    if wrong_regions:
        wrong_regions_text = ", ".join(wrong_regions)
        return (
            f"The following regions do not correspond to expected values: "
            f"{wrong_regions_text}"
        )

    return True


def validate_unique_sample_id(data):
    sample_id_map = {}  # To store the first occurrence of each Sample_ID
    duplicates = []

    for row_index, row in enumerate(
        data.values(), start=2
    ):  # Start from 2 to account for the header
        sample_id = row["sample_id"]

        if sample_id in sample_id_map:
            # Record the duplicate occurrence
            duplicates.append((sample_id_map[sample_id], row_index))
        else:
            # Store the first occurrence of the Sample_ID
            sample_id_map[sample_id] = row_index

    if duplicates:
        duplicate_messages = [
            f"Duplicate Sample_ID found in rows {first} and {second}"
            for first, second in duplicates
        ]
        return "; ".join(duplicate_messages)

    return True


def validate_csv(file_path):
    column_names = get_csv_columns(file_path)

    valid_names = validate_csv_column_names(column_names)

    if valid_names is True:
        data = get_csv_data(file_path)

        unique_sample_id_validation = validate_unique_sample_id(data)
        if unique_sample_id_validation is not True:
            return unique_sample_id_validation

        valid_buckets = validate_csv_buckets(data, column_names)
        if valid_buckets is True:
            return True
        else:
            return valid_buckets
    else:
        return valid_names


def get_sequences_based_on_primers(forward_primer, reverse_primer):
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    regions_file_path = os.path.join(
        base_dir, "metadataconfig", "primer_set_regions.json"
    )

    # Load the JSON file
    with open(regions_file_path, "r") as f:
        primer_set_region = json.load(f)

    # Construct the key to search in the JSON
    search_key = f"{forward_primer}/{reverse_primer}"

    # Check if the key exists in the JSON
    if search_key in primer_set_region:
        region_data = primer_set_region[search_key]
        return {
            "Region": region_data.get("Region"),
            "Forward Primer": region_data.get("Forward Primer"),
            "Reverse Primer": region_data.get("Reverse Primer"),
        }
    else:
        return None
