import pandas as pd
import logging
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
from helpers.metadata_check import get_columns_data

logger = logging.getLogger("my_app_logger")

def create_template():
    # Fetch the metadata
    metadata = get_columns_data()
    logger.debug(f"Metadata: {metadata}")

    # Create a DataFrame with columns based on the metadata keys
    columns = list(metadata.keys())
    df = pd.DataFrame(columns=columns)

    # Add a sample row with example data
    sample_row = {col: 'Sample' if 'options' not in details else details['options'][0] for col, details in metadata.items()}
    df = pd.concat([df, pd.DataFrame([sample_row])], ignore_index=True)

    logger.debug(f"Sample row added to DataFrame: {sample_row}")

    # Create a new Excel workbook and select the active worksheet
    wb = Workbook()
    ws = wb.active

    # Append the DataFrame to the worksheet
    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)

    # Iterate through the metadata to find columns with 'options'
    for col, details in metadata.items():
        if 'options' in details:
            options = details['options']
            dv = DataValidation(
                type="list",
                formula1=f'"{",".join(options)}"',
                showDropDown=True
            )
            ws.add_data_validation(dv)
            col_idx = df.columns.get_loc(col) + 1  # Get column index (1-based)
            for row in range(2, 102):  # Assuming you want to apply it to the first 100 rows
                dv.add(ws.cell(row=row, column=col_idx))

    # Save the workbook
    file_path = 'template_with_dropdowns_for_one_drive.xlsx'
    wb.save(file_path)
    logger.info(f"Template with dropdowns saved as {file_path}")
    

def create_template_one_drive():
    # Fetch the metadata
    metadata = get_columns_data()
    logger.debug(f"Metadata: {metadata}")

    # Create a DataFrame with columns based on the metadata keys
    columns = list(metadata.keys())
    df = pd.DataFrame(columns=columns)

    # Add a sample row with example data
    sample_row = {col: 'Sample' if 'options' not in details else details['options'][0] for col, details in metadata.items()}
    df = pd.concat([df, pd.DataFrame([sample_row])], ignore_index=True)

    logger.debug(f"Sample row added to DataFrame: {sample_row}")

    # Create a new Excel workbook and select the active worksheet
    wb = Workbook()
    ws = wb.active

    # Append the DataFrame to the worksheet
    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)

    # Iterate through the metadata to find columns with 'options'
    for col, details in metadata.items():
        if 'options' in details:
            options = details['options']
            dv = DataValidation(
                type="list",
                formula1=f'"{",".join(options)}"',
                showDropDown=True  # Set to True for visible dropdowns
            )
            ws.add_data_validation(dv)
            col_idx = df.columns.get_loc(col) + 1  # Get column index (1-based)
            col_letter = get_column_letter(col_idx)
            # Apply validation to each cell individually
            for row in range(2, 102):  # Assuming you want to apply it to the first 100 rows
                cell = ws.cell(row=row, column=col_idx)
                dv.add(cell)

    # Save the workbook
    file_path = 'template_with_dropdowns.xlsx'
    try:
        wb.save(file_path)
        logger.info(f"Template with dropdowns saved as {file_path}")
    except Exception as e:
        logger.error(f"Failed to save the workbook: {e}")
    