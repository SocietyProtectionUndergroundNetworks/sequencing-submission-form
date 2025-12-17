import os
import re
import math
import logging
import json
import pandas as pd
from unidecode import unidecode
from collections import defaultdict
from flask_login import current_user

logger = logging.getLogger("my_app_logger")


def get_columns_data(exclude=True):
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    columns_file_path = os.path.join(
        base_dir, "metadataconfig", "columns.json"
    )

    # Load the main configuration JSON
    with open(columns_file_path, "r") as columns_file:
        data = json.load(columns_file)

    # Process each item in the data
    for key, value in list(data.items()):
        # Exclude fields with "excludeFromTemplate": "True" if exclude is True
        if exclude and value.get("excludeFromTemplate") == "True":
            del data[key]  # Remove the key from the data
            continue

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

            # Check for allowAdminNA and if the user is an admin
            if (
                current_user.is_authenticated
                and current_user.admin
                and value.get("allowAdminNA") == "True"
            ):
                value["options"].append("NA")

    return data


def normalize_value(value, options):
    """
    Normalize a value against a list of allowed options.
    Returns the canonical option if matched (case-insensitive),
    otherwise returns the original value.
    """
    if value is None:
        return None

    if not options:
        return value

    value_str = str(value).strip()

    for opt in options:
        if value_str.lower() == str(opt).lower():
            return opt  # canonical case from lookup

    return value


def normalize_row(datadict, columns_data):
    """
    Normalize a row dict using columns metadata.
    """
    normalized = {}

    for col, value in datadict.items():
        column_meta = columns_data.get(col)

        if column_meta and "options" in column_meta:
            normalized[col] = normalize_value(value, column_meta["options"])
        else:
            normalized[col] = value

    return normalized


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


def check_sample_id(sample_id):
    """
    Check if a given SampleID follows the format:
    Any combination of letters, numbers, and underscores
    followed by an underscore and then one or more digits.
    """
    sample_id_str = str(
        sample_id
    ).strip()  # Ensure no leading/trailing whitespace

    # Check if it is empty
    if not sample_id_str:
        return {"status": 0, "message": "SampleID cannot be empty"}

    # Check if it contains invalid characters (anything other than
    # letters, numbers, and underscores)
    if not re.match(r"^[A-Za-z0-9_]+$", sample_id_str):
        return {
            "status": 0,
            "message": (
                "SampleID contains invalid characters. "
                "Only letters, numbers, and underscores are allowed."
            ),
        }

    return {"status": 1, "message": "Valid value"}


def check_sequencing_facility(value):
    return check_field_length_value(value, 150)


def check_vegetation(value):
    return check_field_length_value(value, 200)


def check_soil_depth(value):
    # in 2025-04-10 we changed the accepted values
    # but because templates were out in the world
    # and data would keep coming in with the old values
    # we would have to continue accepting them
    # So for this field we overide the json of the values
    # and we check the validity with a function
    # accepting both old and new values
    if value in [
        "0-20cm",
        "20cm-40cm",
        "40cm-60cm",
        "60cm-80cm",
        "80cm-1m",
        "1m+",
        "0-10cm",
        "10-20cm",
        "20cm-30cm",
        "30cm-1m",
        "1m+",
    ]:
        return {"status": 1, "message": "Valid value"}
    else:
        return {"status": 0, "message": "Not an accepted soil depth"}


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


def build_canonical_lookup(valid_values):
    """
    Build a mapping of lowercase value → canonical value
    """
    return {str(v).strip().lower(): v for v in valid_values}


def check_field_values_lookup(df, valid_values, field_name, allow_empty=True):
    """
    Check if field_name values are valid based on the valid_values list.
    Case-insensitive validation using canonical values.
    """
    canonical_map = build_canonical_lookup(valid_values)
    valid_lower = set(canonical_map.keys())

    invalid_values = []

    for idx, value in df[field_name].items():
        # Handle empty values
        if value is None or (isinstance(value, float) and pd.isna(value)):
            if not allow_empty:
                invalid_values.append({"row": idx, "value": value})
            continue

        value_str = str(value).strip()

        if value_str == "":
            if not allow_empty:
                invalid_values.append({"row": idx, "value": value})
            continue

        # Case-insensitive comparison
        if value_str.lower() not in valid_lower:
            invalid_values.append({"row": idx, "value": value})

    if invalid_values:
        return {
            "invalid": invalid_values,
            "message": f"Invalid {field_name} values",
            "status": 0,
        }

    return {"status": 1}


def check_date_collected(date):
    """
    Check if a single Date_collected value is in YYYY-MM-DD format.
    """
    # Regular expression for YYYY-MM-DD format
    date_format = r"\b\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\b"

    if not re.match(date_format, str(date)):
        return {"status": 0, "message": "Invalid value"}
    else:
        return {"status": 1, "message": "Valid value"}


def check_dna_concentration(value):
    """
    Check if a single DNA_concentration_ng_ul value is a valid numeric value.
    """
    if not is_numeric(value):
        return {
            "status": 0,
            "message": "Invalid value. Only numeric values are allowed",
        }
    else:
        return {"status": 1, "message": "Valid value"}


def check_elevation(value):
    """
    Check if a single elevation value is a valid positive integer.
    """
    if not is_positive_integer(value):
        return {
            "status": 0,
            "message": (
                "Invalid value. Only " "positive integer values are allowed"
            ),
        }
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

    # Check if the input contains any invalid characters like ° or letters
    # Pattern to detect any non-numeric characters (except '.' and '-')
    special_characters_pattern = r"[^\d\.\-]"
    if re.search(special_characters_pattern, str(value)):
        return {
            "status": 0,
            "message": (
                "Invalid value: contains special "
                "characters like degree symbol (°) or letters"
            ),
        }

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
                        "Invalid value: incorrect precision for latitude"
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
                        "Invalid value: incorrect " "precision for longitude"
                    ),
                }

        else:
            return {"status": 0, "message": "Invalid value: out of range"}

    except ValueError:
        return {"status": 0, "message": "Invalid value: not a valid number"}


def check_metadata(df, using_scripps):
    """
    Check metadata including columns, and validity of fields.
    """
    expected_columns_data = get_columns_data(exclude=True)
    overall_status = 1
    issues = {}
    messages = []

    for key, value in expected_columns_data.items():
        if "required" in value and value["required"] == "IfNotScripps":
            value["required"] = using_scripps.lower() != "yes"

    # Check for presence of "Control" in "Sample_or_Control" column
    if "Sample_or_Control" in df.columns:
        if "Control" not in df["Sample_or_Control"].values:
            messages.append(
                "Please note: There is no control in your samples."
            )

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

    # Check for duplicate SampleID values
    if "SampleID" in df.columns:
        duplicates = df[df.duplicated(subset="SampleID", keep=False)]
        if not duplicates.empty:
            duplicate_entries = []
            for idx, value in duplicates.iterrows():
                duplicate_entries.append(
                    {
                        "row": idx,
                        "value": value["SampleID"],
                        "message": "Duplicate SampleID value found",
                    }
                )
            issues["SampleID"] = {
                "status": 0,
                "message": "Duplicate SampleID values found.",
                "invalid": duplicate_entries,
            }
            overall_status = 0

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

        allow_admin_na = (
            column_values.get("allowAdminNA", False) == "True"
            and current_user.admin
        )

        # Check if the field is required but has empty values
        column_data = row[column_key]
        if column_values.get("required", False):
            if (
                column_data is None
                or column_data == ""
                or (isinstance(column_data, float) and math.isnan(column_data))
            ):
                if not allow_admin_na:
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
        if "check_function" in column_values:
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
        elif "options" in column_values:
            options_check_result = check_field_values_lookup(
                pd.DataFrame([row]),
                column_values["options"],
                column_key,
                allow_admin_na,
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

    row_result = {"status": row_status}
    row_result.update(row_issues)

    return row_result


def get_primer_sets_regions():
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    regions_file_path = os.path.join(
        base_dir, "metadataconfig", "primer_set_regions.json"
    )

    # Load the JSON file
    with open(regions_file_path, "r") as f:
        primer_set_regions = json.load(f)

    return primer_set_regions


def primers_forward_to_reverse(primer_set_regions):

    forward_to_reverse = defaultdict(list)

    for key in primer_set_regions:
        forward, reverse = key.split("/")
        if reverse not in forward_to_reverse[forward]:
            forward_to_reverse[forward].append(reverse)
    return forward_to_reverse


def get_sequences_based_on_primers(forward_primer, reverse_primer):
    primer_set_region = get_primer_sets_regions()

    # Construct the key to search in the JSON
    search_key = f"{forward_primer}/{reverse_primer}"

    # Check if the key exists in the JSON
    if search_key in primer_set_region:
        region_data = primer_set_region[search_key]
        # Build the result dictionary dynamically
        result = {
            "Region": region_data.get("Region"),
            "Forward Primer": region_data.get("Forward Primer"),
            "Reverse Primer": region_data.get("Reverse Primer"),
        }

        # Optionally add revcomp values if they exist
        if "Forward Primer Revcomp" in region_data:
            result["Forward Primer Revcomp"] = region_data[
                "Forward Primer Revcomp"
            ]

        if "Reverse Primer Revcomp" in region_data:
            result["Reverse Primer Revcomp"] = region_data[
                "Reverse Primer Revcomp"
            ]

        return result
    else:
        return None


def sanitize_string(s):
    # Escape quotes, special characters,
    # and transliterate non-Latin characters.
    if isinstance(s, str):
        # Transliterate non-Latin characters to Latin equivalents
        s = unidecode(s)
        # Escape double quotes
        s = s.replace('"', '\\"')
        # Escape newline characters
        s = s.replace("\n", "\\n")
        # Escape backslashes
        s = s.replace("\\", "\\\\")
    return s


def sanitize_data(data):
    """Recursively sanitize the input data."""
    if isinstance(data, list):
        return [
            sanitize_data(item) for item in data
        ]  # Sanitize each item in the list
    elif isinstance(data, dict):
        return {
            key: sanitize_data(value) for key, value in data.items()
        }  # Sanitize each value in the dict
    else:
        return sanitize_string(
            data
        )  # Escape string if it's not a list or dict


def build_region_primer_dict(process_data):
    region_primer_dict = {}

    for i in [1, 2]:
        region_key = f"region_{i}"
        forward_key = f"{region_key}_forward_primer"
        reverse_key = f"{region_key}_reverse_primer"

        region_name = process_data[region_key]
        forward_name = process_data[forward_key]
        reverse_name = process_data[reverse_key]

        # Get primer sequences
        primer_seqs = get_sequences_based_on_primers(
            forward_name, reverse_name
        )
        if primer_seqs:
            # Use .get() to safely access keys, fallback
            # to empty string if not found
            region_primer_dict[region_name] = {
                "Forward Primer": primer_seqs.get("Forward Primer", ""),
                "Forward Primer Revcomp": primer_seqs.get(
                    "Forward Primer Revcomp", ""
                ),
                "Reverse Primer": primer_seqs.get("Reverse Primer", ""),
                "Reverse Primer Revcomp": primer_seqs.get(
                    "Reverse Primer Revcomp", ""
                ),
            }

    return region_primer_dict
