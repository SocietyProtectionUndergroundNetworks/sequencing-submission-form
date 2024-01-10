import csv
from helpers.bucket import list_buckets

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
    with open(file_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        first_row = next(reader)  # Get the first row (column names)

        expected_column_names = [
            'Sample_ID',
            'Sequencer_ID',
            'Sequencing_provider',
            'Project',
            'Region',
            'Index_1',
            'Barcode_2'
        ]

        # Compare column names and return a list of mismatched columns
        mismatched_columns = [col for col in first_row if col not in expected_column_names]

        if mismatched_columns:
            mismatched_columns_text = ", ".join(mismatched_columns)
            return f"The following columns do not have expected names: {mismatched_columns_text}"
        return True  # Return True if column names match
        
def validate_csv_buckets(file_path):
    # Get bucket information
    bucket_info = list_buckets()

    expected_regions = [
        'ITS2',
        'ITS1',
        'SSU',
        'LSU',
        'Other'
    ]

    # To store CSV values that do not exist as buckets
    not_found = []
    wrong_regions = []

    with open(file_path, 'r') as file:
        reader = csv.reader(file)
        
        # Skip the header row
        next(reader, None)
        
        for row in reader:
            # Assuming the fourth column contains values
            csv_bucket_value = row[3] if len(row) > 3 else None
            
            # Check if the CSV value exists as a key in the bucket_info dictionary
            if csv_bucket_value not in bucket_info:
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