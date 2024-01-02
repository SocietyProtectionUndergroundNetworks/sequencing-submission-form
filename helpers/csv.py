import csv
from flask import current_app as app  # Import the 'app' instance
    
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
        
        #app.logger.debug(f'First row column names: {first_row}')
        #app.logger.debug(f'Expected column names: {expected_column_names}')

        # Compare column names and return a list of mismatched columns
        mismatched_columns = [col for col in expected_column_names if col not in first_row]

        if mismatched_columns:
            return mismatched_columns  # Return the list of mismatched columns
        return True  # Return True if column names match
