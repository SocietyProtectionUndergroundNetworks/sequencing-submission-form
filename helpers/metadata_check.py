import os
import re
import logging

logger = logging.getLogger("my_app_logger")


def check_sample_id(sample_id):
    """
    Check if a given SampleID follows the format:
    location name (letters), followed by year (two digits),
    an underscore, and a sample number (one or more digits).
    """
    sample_id_pattern = re.compile(r"^[A-Za-z]+[0-9]{2}_[0-9]+$")
    return bool(sample_id_pattern.match(sample_id))


def check_expected_columns(df):
    """
    Check for missing and extra columns in the DataFrame.
    """
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    columns_file_path = os.path.join(base_dir, "metadataconfig", "columns.csv")

    with open(columns_file_path, "r") as columns_file:
        expected_columns = columns_file.read().strip().split("\n")

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


def check_vegetation_length(df):
    """
    Check if the Vegetation column values exceed 200 characters.
    """
    long_vegetation_entries = [
        {"row": idx, "value": value[:20] + "..."}
        for idx, value in df[df["Vegetation"].str.len() > 200][
            "Vegetation"
        ].items()
    ]

    if long_vegetation_entries:
        return {
            "status": 0,
            "invalid": long_vegetation_entries,
            "message": "Invalid Vegetation values exceed 200 characters.",
        }

    return {"status": 1}


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


def check_field_values_lookup(df, field_name, filename, allow_empty=True):
    """
    Check if field_name values are valid based on the filename file.
    """
    current_dir = os.path.dirname(__file__)
    base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    file_path = os.path.join(base_dir, "metadataconfig", filename)

    with open(file_path, "r") as values_file:
        valid_values = values_file.read().strip().split("\n")

    invalid_values = [
        {"row": idx, "value": value}
        for idx, value in df[field_name].dropna().items()
        if (value.strip() == "" and not allow_empty)
        or (value not in valid_values)
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
    invalid_dna_concentration_entries = []
    empty_dna_concentration_entries = []

    for idx, value in df["DNA_concentration_ng_ul"].items():
        if not is_numeric(value) or float(value) < 0:
            invalid_dna_concentration_entries.append(
                {"row": idx, "value": value}
            )

    empty_values = df[
        df["DNA_concentration_ng_ul"].isna()
        | df["DNA_concentration_ng_ul"].astype(str).str.strip().eq("")
    ].index.tolist()

    result = {
        "status": (
            1
            if not invalid_dna_concentration_entries
            and not empty_dna_concentration_entries
            else 0
        ),
        "message": (
            "Invalid DNA_concentration_ng_ul values"
            if invalid_dna_concentration_entries
            or empty_dna_concentration_entries
            else "DNA_concentration_ng_ul values are valid"
        ),
        "invalid": invalid_dna_concentration_entries,
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


def check_metadata(df):
    """
    Check metadata including columns, and validity of fields.
    """
    result = check_expected_columns(df)

    # Initialize the result to collect all issues
    overall_status = 1
    issues = {}

    # Check for columns issues
    if isinstance(result, list):  # Check if result is a list of issues
        for issue in result:
            if issue["status"] == 0:
                overall_status = 0
                if "missing_columns" in issue:
                    issues["missing_columns"] = issue
                elif "extra_columns" in issue:
                    issues["extra_columns"] = issue

    # Check SampleID
    sample_id_check_result = check_sample_ids(df)
    if sample_id_check_result["status"] == 0:
        overall_status = 0
        issues["SampleID"] = sample_id_check_result

    # Check Land_use
    land_use_check_result = check_field_values_lookup(
        df, "Land_use", "landuses.csv", False
    )
    if land_use_check_result["status"] == 0:
        overall_status = 0
        issues["Land_use"] = land_use_check_result

    # Check Country
    country_check_result = check_field_values_lookup(
        df, "Country", "countries.csv", False
    )
    if country_check_result["status"] == 0:
        overall_status = 0
        issues["Country"] = country_check_result

    # Check Vegetation length
    vegetation_length_check_result = check_vegetation_length(df)
    if vegetation_length_check_result["status"] == 0:
        overall_status = 0
        issues["Vegetation"] = vegetation_length_check_result

    # Check Agricultural_land values
    agricultural_land_check_result = check_agricultural_land_values(df)
    if agricultural_land_check_result["status"] == 0:
        overall_status = 0
        issues["Agricultural_land"] = agricultural_land_check_result

    # Check Grid_Size values
    grid_size_check_result = check_field_values_lookup(
        df, "Grid_Size", "gridsizes.csv", False
    )
    if grid_size_check_result["status"] == 0:
        overall_status = 0
        issues["Grid_Size"] = grid_size_check_result

    # Check Soil_depth values
    soil_depth_check_result = check_field_values_lookup(
        df, "Soil_depth", "soildepths.csv", False
    )
    if soil_depth_check_result["status"] == 0:
        overall_status = 0
        issues["Soil_depth"] = soil_depth_check_result

    # Check Transport_refrigeration values
    transport_refrigeration_check_result = check_field_values_lookup(
        df, "Transport_refrigeration", "transport_refrigerations.csv", False
    )
    if transport_refrigeration_check_result["status"] == 0:
        overall_status = 0
        issues["Transport_refrigeration"] = (
            transport_refrigeration_check_result
        )

    # Check Drying values
    drying_check_result = check_field_values_lookup(
        df, "Drying", "dryings.csv", False
    )
    if drying_check_result["status"] == 0:
        overall_status = 0
        issues["Drying"] = drying_check_result

    # Check Ecosystem values
    ecosystem_check_result = check_field_values_lookup(
        df, "Ecosystem", "ecosystems.csv", False
    )
    if ecosystem_check_result["status"] == 0:
        overall_status = 0
        issues["Ecosystem"] = ecosystem_check_result

    # Check Ecosystem values
    date_collected_check_result = check_date_collected(df)
    if date_collected_check_result["status"] == 0:
        overall_status = 0
        issues["Date_collected"] = date_collected_check_result

    # Check Ecosystem values
    extraction_methods_check_result = check_field_values_lookup(
        df, "Extraction_method", "extraction_methods.csv", False
    )
    if extraction_methods_check_result["status"] == 0:
        overall_status = 0
        issues["Extraction_method"] = extraction_methods_check_result

    # Check DNA_concentration_ng_ul values
    dna_concentration_check_result = check_dna_concentration(df)
    if dna_concentration_check_result["status"] == 0:
        overall_status = 0
        issues["DNA_concentration_ng_ul"] = dna_concentration_check_result

    # Combine status and issues into the final result
    final_result = {"status": overall_status}
    final_result.update(issues)

    return final_result
