import os
import re
import math
import logging
import json
import pandas as pd


logger = logging.getLogger("my_app_logger")


def get_columns_data():
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    columns_file_path = os.path.join(
        base_dir, "metadataconfig", "columns.json"
    )

    # Load the main configuration JSON
    with open(columns_file_path, "r") as columns_file:
        data = json.load(columns_file)

    # Process each item in the data
    for key, value in data.items():
        lookup_file = value.get("lookup_file")
        if (
            lookup_file and lookup_file.strip()
        ):  # Check if lookup_file is not empty
            lookup_file_path = os.path.join(
                base_dir, "metadataconfig", lookup_file
            )
            if os.path.exists(lookup_file_path) and lookup_file_path.endswith(
                ".json"
            ):
                with open(lookup_file_path, "r") as lookup:
                    value["options"] = json.load(lookup)
            else:
                value["options"] = []  # Handle missing or unsupported files

    return data


def get_project_common_data():
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    columns_file_path = os.path.join(
        base_dir, "metadataconfig", "project_common_data.json"
    )

    # Load the primary JSON configuration
    with open(columns_file_path, "r") as columns_file:
        data = json.load(columns_file)

    # Process each item in the data
    for key, value in data.items():
        lookup_file = value.get("lookup_file")
        if (
            lookup_file and lookup_file.strip()
        ):  # Check if lookup_file is not empty
            lookup_file_path = os.path.join(
                base_dir, "metadataconfig", lookup_file
            )
            if os.path.exists(lookup_file_path) and lookup_file_path.endswith(
                ".json"
            ):
                with open(lookup_file_path, "r") as lookup:
                    value["options"] = json.load(lookup)
            else:
                value["options"] = []  # Handle missing or unsupported files

    return data


def get_regions(process_data=None):
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    regions_file_path = os.path.join(
        base_dir, "metadataconfig", "primer_set_regions.json"
    )

    # Load the JSON file
    with open(regions_file_path, "r") as f:
        primer_set_region = json.load(f)

    # Check if process_data exists
    if process_data is None:
        # If process_data does not exist, return all available regions
        data = list(primer_set_region.values())
    else:
        # If process_data exists, get the relevant regions for the
        # specified primer sets
        primer_set_1 = process_data.get("Primer_set_1")
        primer_set_2 = process_data.get("Primer_set_2")

        data = []
        if primer_set_1 in primer_set_region:
            data.append(primer_set_region[primer_set_1])
        if primer_set_2 in primer_set_region:
            data.append(primer_set_region[primer_set_2])

    return data


def check_expected_columns(df, expected_columns_data):
    """
    Check for missing and extra columns in the DataFrame.
    """

    expected_columns = list(expected_columns_data.keys())
    uploaded_columns = df.columns.tolist()
    missing_columns = list(set(expected_columns) - set(uploaded_columns))
    extra_columns = list(set(uploaded_columns) - set(expected_columns))
    issues = []

    if missing_columns:
        issues.append(
            {
                "invalid": missing_columns,
                "message": "Missing columns",
                "status": 0,
            }
        )

    if extra_columns:
        issues.append(
            {"invalid": extra_columns, "message": "Extra columns", "status": 0}
        )
    return issues


def check_sample_id(sample_id):
    """
    Check if a given SampleID follows the format:
    location name (letters), followed by year (two digits),
    an underscore, and a sample number (one or more digits).
    """
    sample_id_pattern = re.compile(r"^[A-Za-z]+[0-9]{2}_[0-9]+$")
    if not sample_id_pattern.match(str(sample_id)):
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def check_sequencing_facility(value):
    return check_field_length_value(value, 150)


def check_vegetation(value):
    return check_field_length_value(value, 200)


def check_expedition_lead(value):
    return check_field_length_value(value, 150)


def check_notes(value):
    return check_field_length_value(value, 200)


def check_collaborators_value(value):
    return check_field_length_value(value, 150)


def check_field_length_value(value, max_length):
    """
    Check if a single value's length does not exceed
    the specified maximum length.
    """
    if len(str(value)) > max_length:
        return {
            "status": 0,
            "message": f"Value exceeds maximum length of {max_length}",
        }
    else:
        return {"status": 1, "message": "Valid value"}


def check_agricultural_land_value(value):
    """
    Check if a single Agricultural_land value is valid ('yes' or 'no').
    """
    if value not in ["yes", "no"]:
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def check_field_values_lookup(df, valid_values, field_name, allow_empty=True):
    """
    Check if field_name values are valid based on the valid_values list.
    Ignore case when comparing values.
    """
    invalid_values = [
        {"row": idx, "value": value}
        for idx, value in df[field_name].dropna().items()
        if (
            (value.strip() == "" and not allow_empty)
            or (value.strip().lower() not in [v.lower() for v in valid_values])
        )
    ]

    # Identify empty values
    empty_values = []
    if not allow_empty:
        empty_values = df[
            df[field_name].isna()
            | df[field_name].astype(str).str.strip().eq("")
        ].index.tolist()

    if invalid_values or empty_values:
        return {
            "invalid": invalid_values,
            "empty_values": empty_values,
            "message": (
                "Invalid " + field_name + " values"
                if invalid_values
                else "Empty values found for " + field_name
            ),
            "status": 0,
        }
    else:
        return {"status": 1}


def check_date_collected(date):
    """
    Check if a single Date_collected value is in YYYY-MM-DD format.
    """
    # Regular expression for YYYY-MM-DD format
    date_format = r"\b\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\b"
    logger.info(date)

    if not re.match(date_format, str(date)):
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def check_dna_concentration(value):
    """
    Check if a single DNA_concentration_ng_ul value is a valid numeric value.
    """
    if not is_numeric(value):
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def check_elevation(value):
    """
    Check if a single elevation value is a valid positive integer.
    """
    if not is_positive_integer(value):
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def is_numeric(value):
    """
    Check if a value is a numeric decimal.
    """
    try:
        float(value)
        return True
    except ValueError:
        return False


def is_positive_integer(value):
    """
    Check if a value is a positive integer.
    """
    try:
        # Check if the value can be converted to an integer
        int_value = int(value)
        # Check if the integer value is positive
        if int_value > 0:
            return True
        else:
            return False
    except ValueError:
        return False


def check_latitude_longitude(value):
    """
    Check if a single latitude or longitude value is in decimal
    format (WGS1984) and valid.
    """

    try:
        float_value = float(value)

        # Define regex pattern for up to 15 decimal places
        pattern = r"^-?\d+(\.\d{1,15})?$"

        # Check if it's a valid latitude
        if -90 <= float_value <= 90:
            if re.match(
                pattern, str(float_value)
            ):  # Check precision up to 15 decimal places
                return {"status": 1, "message": "Valid latitude"}
            else:
                return {
                    "status": 0,
                    "message": (
                        "Invalid value: incorrect "
                        "precision for latitude"
                    ),
                }

        # Check if it's a valid longitude
        elif -180 <= float_value <= 180:
            if re.match(
                pattern, str(float_value)
            ):  # Check precision up to 15 decimal places
                return {"status": 1, "message": "Valid longitude"}
            else:
                return {
                    "status": 0,
                    "message": (
                        "Invalid value: incorrect "
                        "precision for longitude"
                    ),
                }

        else:
            return {"status": 0, "message": "Invalid value: out of range"}

    except ValueError:
        return {"status": 0, "message": "Invalid value: not a valid number"}


def check_metadata(df, using_scripps, multiple_sequencing_runs=False):
    """
    Check metadata including columns, and validity of fields.
    """
    expected_columns_data = get_columns_data()
    overall_status = 1
    issues = {}
    messages = []

    for key, value in expected_columns_data.items():
        if "required" in value and value["required"] == "IfNotScripps":
            if using_scripps == "no":
                value["required"] = True
            else:
                value["required"] = False

    # Check for presence of "Control" in "Sample_or_Control" column
    if "Sample_or_Control" in df.columns:
        if "Control" not in df["Sample_or_Control"].values:
            messages.append(
                "Please note: There is no control in your samples."
            )

    if multiple_sequencing_runs == "Yes":
        if "SequencingRun" in expected_columns_data:
            expected_columns_data["SequencingRun"]["required"] = True

            # Check if there is more than one unique value in
            # the SequencingRun field
            unique_sequencing_runs = df["SequencingRun"].nunique()
            if unique_sequencing_runs <= 1:
                issues["SequencingRun"] = {
                    "status": 0,
                    "message": (
                        "Multiple sequencing runs indicated but "
                        "only one unique value "
                        "found in SequencingRun field"
                    ),
                    "invalid": [],
                }
                overall_status = 0

    for column_key, column_values in expected_columns_data.items():
        if column_key not in df.columns:
            if column_values.get("required", False):
                issues[column_key] = {
                    "status": 0,
                    "message": f"Required column {column_key} is missing",
                    "missing": True,
                }
                overall_status = 0
            continue  # Skip further checks for missing columns

    # Check each row using the check_row function
    for idx, row in df.iterrows():
        row_result = check_row(row, expected_columns_data)
        if row_result["status"] == 0:
            overall_status = 0
            for key, value in row_result.items():
                if key != "status":
                    if key not in issues:
                        issues[key] = {
                            "status": 0,
                            "invalid": [],
                            "message": value["message"],
                        }
                    issues[key]["invalid"].extend(value["invalid"])

    final_result = {"status": overall_status}
    final_result.update(issues)

    if messages:
        final_result["messages"] = messages

    return final_result


def check_row(row, expected_columns_data):
    """
    Validate a single row of data.
    """
    # Skip checks if "Sample_or_Control" column
    # exists and its value is "Control"
    if (
        "Sample_or_Control" in row.index
        and row["Sample_or_Control"] == "Control"
    ):
        return {"status": 1}

    row_issues = {}
    row_status = 1

    for column_key, column_values in expected_columns_data.items():
        if column_key not in row.index:
            continue  # Skip missing columns

        # Check if the field is required but has empty values
        column_data = row[column_key]
        if column_values.get("required", False):
            if (
                column_data is None
                or column_data == ""
                or (isinstance(column_data, float) and math.isnan(column_data))
            ):
                row_issues[column_key] = {
                    "status": 0,
                    "invalid": [
                        {
                            "row": row.name,
                            "value": "",
                            "message": (
                                f"Required column {column_key} \
                                has empty values"
                            ),
                        }
                    ],
                    "message": (
                        f"Required column {column_key} has empty values"
                    ),
                }
                row_status = 0
                # Skip further checks for this column if empty values found
                continue

        # Perform specific checks based on the type of validation
        if "options" in column_values:
            options_check_result = check_field_values_lookup(
                pd.DataFrame([row]), column_values["options"], column_key
            )
            if options_check_result["status"] == 0:
                row_status = 0
                row_issues[column_key] = {
                    "status": 0,
                    "invalid": [
                        {
                            "row": row.name,
                            "value": column_data,
                            "message": options_check_result["message"],
                        }
                    ],
                    "message": options_check_result["message"],
                }
        elif "check_function" in column_values:
            check_function_name = column_values["check_function"]
            if check_function_name in globals():
                check_function = globals()[check_function_name]
                if not (
                    column_data is None
                    or column_data == ""
                    or (
                        isinstance(column_data, float)
                        and math.isnan(column_data)
                    )
                ):
                    check_result = check_function(column_data)
                    if check_result["status"] == 0:
                        row_status = 0
                        row_issues[column_key] = {
                            "status": 0,
                            "invalid": [
                                {
                                    "row": row.name,
                                    "value": column_data,
                                    "message": check_result["message"],
                                }
                            ],
                            "message": (
                                f"Column {column_key} has invalid values"
                            ),
                        }
            else:
                row_status = 0
                row_issues[column_key] = {
                    "status": 0,
                    "invalid": [
                        {
                            "row": row.name,
                            "value": column_data,
                            "message": (
                                f"Check function \
                                {check_function_name} not found"
                            ),
                        }
                    ],
                    "message": (
                        f"Check function {check_function_name} not found"
                    ),
                }

    row_result = {"status": row_status}
    row_result.update(row_issues)

    return row_result


def get_nr_files_per_sequence(sequencing_platform):
    sequencers_expecting_pairs = [
        "Illumina NextSeq",
        "Illumina MiSeq",
        "Illumina NovaSeq",
        "Element Biosciences AVITI",
    ]

    # Strip whitespace
    sequencing_platform = sequencing_platform.strip()

    if sequencing_platform in sequencers_expecting_pairs:
        return 2
    return 1
