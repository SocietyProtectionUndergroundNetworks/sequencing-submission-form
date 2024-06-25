import os
import re
import logging
import json

logger = logging.getLogger("my_app_logger")


def check_sample_id(sample_id):
    """
    Check if a given SampleID follows the format:
    location name (letters), followed by year (two digits),
    an underscore, and a sample number (one or more digits).
    """
    sample_id_pattern = re.compile(r"^[A-Za-z]+[0-9]{2}_[0-9]+$")
    return bool(sample_id_pattern.match(sample_id))


def get_columns_data():
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    columns_file_path = os.path.join(
        base_dir, "metadataconfig", "columns.json"
    )

    with open(columns_file_path, "r") as columns_file:
        data = json.load(columns_file)

    for key, value in data.items():
        lookup_file = value.get("lookup_file")
        if (
            lookup_file and lookup_file.strip()
        ):  # Check if lookup_file is not empty
            lookup_file_path = os.path.join(
                base_dir, "metadataconfig", lookup_file
            )
            if os.path.exists(lookup_file_path):
                with open(lookup_file_path, "r") as lookup:
                    value["options"] = lookup.read().strip().split("\n")
            else:
                value["options"] = []  # or handle missing file as needed

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


def check_sample_ids(df):
    """
    Check the SampleID column for correct format.
    """
    
    invalid_sample_ids = []
    for idx, sample_id in df["SampleID"].items():
        if not check_sample_id(sample_id):
            invalid_sample_ids.append({"row": idx, "value": sample_id})

    if invalid_sample_ids:
        return {
            "status": 0,
            "invalid": invalid_sample_ids,
            "message": "Some SampleID do not follow the required format.",
        }

    return {"status": 1}

def check_field_length(df, field_name, limit):
    """
    Check if the field values exceed limit characters.
    """
    # Replace NaN values with empty strings
    df[field_name] = df[field_name].fillna("")

    # Find entries that exceed the length limit
    long_entries = [
        {"row": idx, "value": value[:20] + "..."}
        for idx, value in df[df[field_name].str.len() > limit][field_name].items()
    ]

    if long_entries:
        return {
            "status": 0,
            "invalid": long_entries,
            "message": f"Invalid {field_name} values exceed {limit} characters.",
        }

    return {"status": 1}

def check_sequencing_facility(df):
    result = check_field_length(df, "Sequencing_facility", 150)
    return result

def check_vegetation(df):
    result = check_field_length(df, "Vegetation", 200)
    return result


def check_expedition_lead(df):
    result = check_field_length(df, "Expedition_lead", 150)
    return result


def check_notes(df):
    result = check_field_length(df, "Notes", 200)
    return result

def check_collaborators(df):
    result = check_field_length(df, "Collaborators", 150)
    return result


def check_agricultural_land_values(df):
    """
    Check if the Agricultural_land column values are valid ('yes' or 'no').
    """
    invalid_values = (
        df["Agricultural_land"].dropna().unique()
    )  # Drop NaN and get unique values
    invalid_values = [
        value for value in invalid_values if value not in ["yes", "no"]
    ]

    if invalid_values:
        return {
            "status": 0,
            "invalid": invalid_values,
            "message": "Invalid Agricultural_land values (not 'yes' or 'no')",
        }

    return {"status": 1}


def check_field_values_lookup(df, valid_values, field_name, allow_empty=True):
    """
    Check if field_name values are valid based on the valid_values list.
    Ignore case when comparing values.
    """
    invalid_values = [
        {"row": idx, "value": value}
        for idx, value in df[field_name].dropna().items()
        if ((value.strip() == "" and not allow_empty) or
            (value.strip().lower() not in [v.lower() for v in valid_values]))
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


def check_date_collected(df):
    """
    Check if Date_collected values are in DD/MM/YYYY
    format and logical coherence.
    """
    date_format = r"\b(?:0[1-9]|[12][0-9]|3[01])/(?:0[1-9]|1[0-2])/\d{4}\b"

    def validate_date(date):
        return re.match(date_format, date)

    dates = df["Date_collected"].dropna()

    invalid_dates = []
    empty_values = []

    for idx, date in dates.items():  # Use items() instead of iteritems()
        if not validate_date(date):
            invalid_dates.append({"row": idx, "value": date})

    empty_values = df[
        df["Date_collected"].isna()
        | df["Date_collected"].astype(str).str.strip().eq("")
    ].index.tolist()

    result = {
        "status": 0 if invalid_dates or empty_values else 1,
        "message": (
            "Invalid Date_collected values"
            if invalid_dates
            else "Date_collected values are valid"
        ),
        "invalid": invalid_dates,
        "empty_values": empty_values,
    }

    return result


def check_dna_concentration(df):
    """
    Check if DNA_concentration_ng_ul values are valid numeric
    decimal values and not empty.
    """
    invalid_entries = []
    empty_values = []

    for idx, value in df["DNA_concentration_ng_ul"].items():
        if not is_numeric(value):
            invalid_entries.append({"row": idx, "value": value})

    empty_values = df[
        df["DNA_concentration_ng_ul"].isna()
        | df["DNA_concentration_ng_ul"].astype(str).str.strip().eq("")
    ].index.tolist()

    result = {
        "status": (1 if not invalid_entries and not empty_values else 0),
        "message": (
            "Invalid DNA_concentration_ng_ul values"
            if invalid_entries or empty_values
            else "DNA_concentration_ng_ul values are valid"
        ),
        "invalid": invalid_entries,
        "empty_values": empty_values,
    }

    return result


def check_elevation(df):
    """
    Check if elevation values are valid numeric
    integer values and not empty.
    """
    invalid_entries = []
    empty_values = []

    invalid_entries = [
        {"row": idx, "value": value}
        for idx, value in df["Elevation"].dropna().items()
        if not is_positive_integer(value)
    ]

    empty_values = df[
        df["Elevation"].isna() | df["Elevation"].astype(str).str.strip().eq("")
    ].index.tolist()

    result = {
        "status": (1 if not invalid_entries and not empty_values else 0),
        "message": (
            "Invalid Elevation values"
            if invalid_entries or empty_values
            else "Elevation values are valid"
        ),
        "invalid": invalid_entries,
        "empty_values": empty_values,
    }

    return result


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


def check_metadata(df):
    """
    Check metadata including columns, and validity of fields.
    """
    expected_columns_data = get_columns_data()
    result = check_expected_columns(df, expected_columns_data)
    # Initialize the result to collect all issues
    overall_status = 1
    issues = {}

    # Identify missing and extra columns
    missing_columns = set()
    extra_columns = set()
    
    if isinstance(result, list):  # Check if result is a list of issues
        for issue in result:
            if issue["status"] == 0:
                overall_status = 0
                if issue['message'] == "Missing columns":
                    missing_columns.update(issue["invalid"])
                    issues["missing_columns"] = issue
                elif issue['message'] == "Extra columns":
                    extra_columns.update(issue["invalid"])
                    issues["extra_columns"] = issue
    

    # Iterate through expected columns data, skipping any missing columns
    for column_key, column_values in expected_columns_data.items():
        if column_key in missing_columns:
            continue  # Skip checks for missing columns

        if "options" in column_values:
            options_check_result = check_field_values_lookup(df, column_values["options"], column_key)
            if options_check_result["status"] == 0:
                overall_status = 0
                issues[column_key] = options_check_result
        elif "check_function" in column_values:
            # Dynamically call the check function
            check_function_name = column_values["check_function"]
            if check_function_name in globals():
                check_function = globals()[check_function_name]
                check_result = check_function(df)
                if check_result["status"] == 0:
                    overall_status = 0
                    issues[column_key] = check_result
            else:
                # Handle the case where the check function is not found
                overall_status = 0
                issues[column_key] = {"status": 0, "message": f"Check function {check_function_name} not found"}

    # Combine status and issues into the final result
    final_result = {"status": overall_status}
    final_result.update(issues)

    return final_result

