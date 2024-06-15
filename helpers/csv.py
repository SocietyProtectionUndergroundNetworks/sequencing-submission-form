import csv
import re
from helpers.bucket import list_buckets
import logging

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def validate_csv(file_path):

    valid_names = validate_csv_column_names(file_path)

    if valid_names is True:
        valid_buckets = validate_csv_buckets(file_path)

        if valid_buckets is True:
            return True
        else:
            return valid_buckets
    else:
        return valid_names


def validate_csv_column_names(file_path):
    with open(file_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)
        first_row = next(reader)  # Get the first row (column names)

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
            col for col in first_row if col not in expected_column_names
        ]

        if mismatched_columns:
            mismatched_columns_text = ", ".join(mismatched_columns)
            return f"The following columns do not have expected names: {mismatched_columns_text}"

        for line_number, row in enumerate(
            reader, start=2
        ):  # Start counting lines from 2 since header is 1st line
            if len(row) != len(expected_column_names):
                return f"Error in line {line_number}: Incorrect number of columns."

        return True  # Return True if column names match


def validate_csv_buckets(file_path):
    # Get bucket information
    bucket_info = list_buckets()

    expected_regions = ["ITS2", "ITS1", "SSU", "LSU", "Other"]

    # To store CSV values that do not exist as buckets
    not_found = []
    wrong_regions = []

    with open(file_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.reader(csvfile)

        # Skip the header row
        next(reader, None)

        for row in reader:
            # Assuming the fourth column contains values
            csv_bucket_value = row[3] if len(row) > 3 else None

            # Check if the CSV value exists as a key in the bucket_info dictionary
            if csv_bucket_value.lower() not in bucket_info:
                not_found.append(csv_bucket_value)

            csv_region_value = row[4] if len(row) > 4 else None
            if csv_region_value not in expected_regions:
                wrong_regions.append(csv_region_value)

    # deduplicate the lists
    not_found = list(set(not_found))
    wrong_regions = list(set(wrong_regions))

    if not_found:
        not_found_text = ", ".join(not_found)
        return f"The following projects do not correspond to buckets: {not_found_text}"

    if wrong_regions:
        wrong_regions_text = ", ".join(wrong_regions)
        return f"The following regions do not correspond to expected values: {wrong_regions_text}"

    return True


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


def get_csv_data(file_path):
    data = {}
    existing_ids = []
    with open(file_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        csv_reader = csv.DictReader(csvfile)
        # next(csv_reader)  # Skip the header row
        for row in csv_reader:
            sample_id_safe = make_safe_html_id(
                row["Sample_ID"]
                + "__"
                + row["Sequencer_ID"]
                + "__"
                + row["Project"],
                existing_ids,
            )
            existing_ids.append(sample_id_safe)
            data[sample_id_safe] = {
                "sample_id": row["Sample_ID"],
                "sequencer_id": row["Sequencer_ID"],
                "sequencer_provider": row["Sequencing_provider"],
                "project": row["Project"],
                "region": row["Region"],
                "index_1": row["Index_1"],
                "index_2": row["Index_2"],
                "sample_id_safe": sample_id_safe,
            }
    return data
