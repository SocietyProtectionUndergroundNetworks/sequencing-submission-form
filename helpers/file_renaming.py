# Script for renaming fastq files received from Scripps Research.  Requires a sample key with file name string matches and desired name changes to be specified in-script. Takes a directory containing the files to be changed as an argument. 

import os
import gzip
import csv
import tarfile

def extract_tar(tar_file, extract_path):
    with tarfile.open(tar_file, 'r') as tar:
        tar.extractall(path=extract_path)

def extract_tar_without_structure(tar_file, extract_path):
    with tarfile.open(tar_file, 'r') as tar:
        for member in tar.getmembers():
            member.name = os.path.basename(member.name)
            tar.extract(member, path=extract_path)

def extract_gzip(uploaded_file_path, file_id, extract_directory):

    # Create the directory if it doesn't exist
    os.makedirs(extract_directory, exist_ok=True)

    # Get the file name from the full path
    uploaded_file_name = os.path.basename(uploaded_file_path)

    # Check if the uploaded file name ends with '.gz'
    if not uploaded_file_name.endswith('.gz'):
        raise ValueError("The uploaded file is not a gzip file.")

    # Get the file name without the '.gz' extension
    file_name = os.path.splitext(uploaded_file_name)[0]

    # Path to extract the file to
    extract_path = os.path.join(extract_directory, file_name)

    # Extract the gzip file
    with gzip.open(uploaded_file_path, 'rb') as f_in:
        with open(extract_path, 'wb') as f_out:
            f_out.write(f_in.read())

    # check if the file is a tar, in which case we have more to do
    if file_name.endswith('.tar'):
        extract_tar_without_structure(extract_path, extract_directory)
        os.remove(extract_path)
    
    return True
    


def rename_file(csv_file, uploaded_file):
    csv_path = os.path.join('uploads', csv_file)

    # Initialize an empty dictionary to store dictionaries with keys as the first value of each row
    data_dict = {}

    # Load the csv file
    with open(csv_path, newline='') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')  # Assuming CSV is comma-separated
        headers = next(csvreader)  # Read the first row as headers

        for row in csvreader:
            key = row[0]  # Get the key (first value of the row)

            if key in ["Description", "Sample Number", "Example", ""] or key is None:
                continue  # Skip this row if the key is empty or matches specific strings

            # Check for duplicate keys
            if key in data_dict:
                raise ValueError(f"Duplicate key found: {key}")

            # Create a dictionary for each row using headers as keys
            row_dict = {header: value for header, value in zip(headers, row)}

            # Check if 'Sequencer_ID' exists and is not empty before printing
            sequencer_id = row_dict.get('Sample_ID', '')
            if sequencer_id and sequencer_id.strip():  # Check if 'Sequencer_ID' is not empty or whitespace
                sampleid = str(sequencer_id)
                print('we have a row for the sampleid ', sampleid)
                print(sampleid.split('id', 1)[0])
                if uploaded_file.startswith(sampleid.split('id', 1)[0] + 'id'):
                    print(row_dict)

            # Add the row dictionary to the data_dict with the key
            data_dict[key] = row_dict

    return "done4"
            
    if False:
        # Load the Excel file
        df = pd.read_excel(excel_path)

        # Iterate through each row in the DataFrame
        for index, row in df.iterrows():
            sampleid = str(row['Sequencer_ID'])
            name = str(row['Sample_ID'])

            # Get a list of all file names in the directory
            file_names = os.listdir(directory_path)

            # Find the matching filenames based on the Sequencer_ID
            matching_files = [filename for filename in file_names if filename.startswith(sampleid.split('id', 1)[0] + 'id')]

            for matching_file in matching_files:
                # Get the full path of the matching file
                old_file_path = os.path.join(directory_path, matching_file)

                # Extract the portion after '_S' from the matching file
                extension = matching_file.split('_S')[-1]

                # Replace 'RIBO' with 'SSU' in the 'Name' column
                if 'RIBO' in name:
                    new_name = name.replace('RIBO', 'SSU')
                else:
                    new_name = name

                # Create the new file name based on the extracted extension, modified 'Name' column, and the 'CCBB' prefix
                new_file_name = new_name + '_S' + extension

                # Check for duplicate names
                if new_file_name in file_names:
                    print(f"Duplicate file name: {new_file_name}. Skipping renaming for {matching_file}")
                else:
                    # Get the full path of the new file name
                    new_file_path = os.path.join(directory_path, new_file_name)

                    # Rename the file
                    os.rename(old_file_path, new_file_path)
                    print(f"Renamed {matching_file} to {new_file_name}")

            if not matching_files:
                print(f"File with SampleID {sampleid} not found in the directory")


def rename_files(excel_file, directory):
    # Get the current working directory
    current_dir = os.getcwd()

    # Create the full paths for the Excel file and the directory
    excel_path = os.path.join(current_dir, excel_file)
    directory_path = os.path.join(current_dir, directory)

    # Load the Excel file
    df = pd.read_excel(excel_path)

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        sampleid = str(row['Sequencer_ID'])
        name = str(row['Sample_ID'])

        # Get a list of all file names in the directory
        file_names = os.listdir(directory_path)

        # Find the matching filenames based on the Sequencer_ID
        matching_files = [filename for filename in file_names if filename.startswith(sampleid.split('id', 1)[0] + 'id')]

        for matching_file in matching_files:
            # Get the full path of the matching file
            old_file_path = os.path.join(directory_path, matching_file)

            # Extract the portion after '_S' from the matching file
            extension = matching_file.split('_S')[-1]

            # Replace 'RIBO' with 'SSU' in the 'Name' column
            if 'RIBO' in name:
                new_name = name.replace('RIBO', 'SSU')
            else:
                new_name = name

            # Create the new file name based on the extracted extension, modified 'Name' column, and the 'CCBB' prefix
            new_file_name = new_name + '_S' + extension

            # Check for duplicate names
            if new_file_name in file_names:
                print(f"Duplicate file name: {new_file_name}. Skipping renaming for {matching_file}")
            else:
                # Get the full path of the new file name
                new_file_path = os.path.join(directory_path, new_file_name)

                # Rename the file
                os.rename(old_file_path, new_file_path)
                print(f"Renamed {matching_file} to {new_file_name}")

        if not matching_files:
            print(f"File with SampleID {sampleid} not found in the directory")



# Example usage
# excel_file = 'Documents/Data/Sample_Key_Run1.csv'  # Provide the name of your Excel file
# directory = 'Data_processing/Utrecht/ITS2'  # Provide the path to the directory containing the files

# rename_files(excel_file, directory)
