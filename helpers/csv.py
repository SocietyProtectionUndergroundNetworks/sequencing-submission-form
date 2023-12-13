import csv
    
def validate_csv_column_names(file_path):
    with open(file_path, 'r', newline='') as csvfile:
        reader = csv.reader(csvfile)
        first_row = next(reader)  # Get the first row (column names)

        expected_column_names = [
            'Sample Number',
            'Sample_ID',
            'Sequencer_ID',
            'Sequencing_provider',
            'Project',
            'Region',
            'Index_1',
            'Barcode_2'
        ]

        if first_row != expected_column_names:
            return False  # Return False if column names don't match
        return True  # Return True if column names match    