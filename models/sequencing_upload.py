import datetime
import random
import string
import logging
import os
import json
import shutil
import csv
from collections import defaultdict
from helpers.dbm import connect_db, get_session
from helpers.fastqc import init_create_fastqc_report, check_fastqc_report
from helpers.csv import get_sequences_based_on_primers
from models.db_model import (
    SequencingUploadsTable,
    SequencingSamplesTable,
    SequencingSequencerIDsTable,
    SequencingFilesUploadedTable,
    UserTable,
)
from pathlib import Path
from flask_login import current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingUpload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.nr_files_per_sequence = 1
        self.regions = []

    @classmethod
    def get(cls, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = (
            session.query(SequencingUploadsTable).filter_by(id=id).first()
        )

        session.close()

        if not upload_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        upload_db_dict = upload_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in upload_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of SequencingUpload using the dictionary
        upload = cls(**filtered_dict)

        upload.nr_files_per_sequence = cls.determine_nr_files_per_sequence(
            filtered_dict["Sequencing_platform"]
        )

        upload.regions = cls.get_regions(
            filtered_dict["region_1_forward_primer"],
            filtered_dict["region_1_reverse_primer"],
            filtered_dict["region_2_forward_primer"],
            filtered_dict["region_2_reverse_primer"],
        )

        # Convert the instance to a dictionary including the custom attribute
        upload_dict = upload.__dict__

        return upload_dict

    @classmethod
    def get_all(cls, user_id=None):
        db_engine = connect_db()
        session = get_session(db_engine)

        query = session.query(SequencingUploadsTable, UserTable).join(
            UserTable, SequencingUploadsTable.user_id == UserTable.id
        )

        if user_id is not None:
            query = query.filter(SequencingUploadsTable.user_id == user_id)

        upload_dbs = query.all()

        uploads = []
        for upload_db, user in upload_dbs:
            upload_db_dict = upload_db.__dict__
            user_dict = user.__dict__

            filtered_dict = {
                key: value
                for key, value in upload_db_dict.items()
                if not key.startswith("_")
            }

            upload = cls(**filtered_dict)

            upload.nr_files_per_sequence = cls.determine_nr_files_per_sequence(
                filtered_dict["Sequencing_platform"]
            )

            upload.regions = cls.get_regions(
                filtered_dict["region_1_forward_primer"],
                filtered_dict["region_1_reverse_primer"],
                filtered_dict["region_2_forward_primer"],
                filtered_dict["region_2_reverse_primer"],
            )

            # Calculate the total size of the uploads folder and
            # count the fastq files
            upload.total_uploads_file_size = 0
            upload.nr_fastq_files = 0
            uploads_folder = filtered_dict["uploads_folder"]
            if uploads_folder:
                total_size, fastq_count = cls.get_directory_size(
                    os.path.join("seq_uploads", uploads_folder)
                )
                upload.total_uploads_file_size = total_size
                upload.nr_fastq_files = fastq_count

            # Calculate the number of regions
            upload.nr_regions = len(upload.regions)

            # Count the number of samples associated with this upload
            nr_samples = (
                session.query(SequencingSamplesTable)
                .filter_by(sequencingUploadId=filtered_dict["id"])
                .count()
            )
            upload.nr_samples = nr_samples

            # Count the number of sequencer IDs associated with this upload
            nr_sequencer_ids = (
                session.query(SequencingSequencerIDsTable)
                .join(
                    SequencingSamplesTable,
                    SequencingSamplesTable.id
                    == SequencingSequencerIDsTable.sequencingSampleId,
                )
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == filtered_dict["id"]
                )
                .count()
            )
            upload.nr_sequencer_ids = nr_sequencer_ids

            # Add user name and email to the upload dictionary
            upload.user_name = user_dict["name"]
            upload.user_email = user_dict["email"]

            upload_dict = upload.__dict__
            uploads.append(upload_dict)

        session.close()

        return uploads

    @staticmethod
    def get_directory_size(directory):
        total_size = 0
        fastq_count = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
                    if f.endswith(".fastq.gz") or f.endswith(".fastq"):
                        fastq_count += 1
        return total_size, fastq_count

    @staticmethod
    def determine_nr_files_per_sequence(sequencing_platform):
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

    @classmethod
    def get_regions(
        cls,
        region_1_forward_primer=None,
        region_1_reverse_primer=None,
        region_2_forward_primer=None,
        region_2_reverse_primer=None,
    ):
        current_dir = os.path.dirname(__file__)
        base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
        regions_file_path = os.path.join(
            base_dir, "metadataconfig", "primer_set_regions.json"
        )

        # Load the JSON file
        with open(regions_file_path, "r") as f:
            primer_set_region = json.load(f)

        # Create a reverse lookup dictionary from primers to region names
        primer_to_region = {
            (key): value["Region"] for key, value in primer_set_region.items()
        }

        # Initialize sets to track unique regions
        primer_set_1_regions = set()
        if region_1_forward_primer and region_1_reverse_primer:
            primer_set_1 = (
                f"{region_1_forward_primer}/{region_1_reverse_primer}"
            )
            if primer_set_1 in primer_to_region:
                primer_set_1_regions.add(primer_to_region[primer_set_1])

        primer_set_2_regions = set()
        if region_2_forward_primer and region_2_reverse_primer:
            primer_set_2 = (
                f"{region_2_forward_primer}/{region_2_reverse_primer}"
            )
            if primer_set_2 in primer_to_region:
                primer_set_2_regions.add(primer_to_region[primer_set_2])

        # Combine regions from both primer sets and return unique regions
        regions = list(primer_set_1_regions.union(primer_set_2_regions))

        return regions

    @classmethod
    def get_samples(self, sequencingUploadId):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch related samples
        samples = (
            session.query(SequencingSamplesTable)
            .filter_by(sequencingUploadId=sequencingUploadId)
            .all()
        )

        # Define the as_dict method within this function
        def as_dict(instance):
            """Convert SQLAlchemy model instance to a dictionary."""
            return {
                column.name: getattr(instance, column.name)
                for column in instance.__table__.columns
            }

        # Convert each sample instance to a dictionary
        samples_list = [as_dict(sample) for sample in samples]

        # Close the session
        session.close()

        return samples_list

    @classmethod
    def create(cls, datadict):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Create a new instance of SequencingUploadsTable
        new_upload = SequencingUploadsTable(
            user_id=current_user.id,
        )

        if datadict["using_scripps"] == "yes":
            datadict["region_1_forward_primer"] = "ITS3"
            datadict["region_1_reverse_primer"] = "ITS4"
            datadict["region_2_forward_primer"] = "WANDA"
            datadict["region_2_reverse_primer"] = "AML2"
            datadict["Sequencing_platform"] = "Element Biosciences AVITI"
            datadict["Sequencing_facility"] = "Scripps Research"

        if (
            datadict["region_2_forward_primer"] == "0"
            and datadict["region_2_reverse_primer"] == "0"
        ):
            datadict["Sequencing_regions_number"] = 1
        else:
            datadict["Sequencing_regions_number"] = 2

        # Dynamically set attributes from datadict
        for key, value in datadict.items():
            if key == "using_scripps":
                value = value.lower() == "yes"
            if hasattr(new_upload, key):
                setattr(new_upload, key, value)

        session.add(new_upload)
        session.commit()

        # Refresh the object to get the updated ID
        session.refresh(new_upload)

        new_upload_id = new_upload.id

        id_str = f"{new_upload_id:05}"

        # lets create a directory only for this process.
        uploads_folder = (
            id_str
            + "_"
            + datetime.datetime.now().strftime("%Y%m%d")
            + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
        )

        path = Path("seq_uploads", uploads_folder)
        path.mkdir(parents=True, exist_ok=True)

        new_upload.uploads_folder = uploads_folder
        session.commit()

        session.close()

        return new_upload_id

    @classmethod
    def get_sequencer_ids(self, sequencingUploadId):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query to get all SequencingSequencerIDsTable
        # entries associated with the given process_id
        sequencer_ids = (
            session.query(SequencingSequencerIDsTable)
            .join(SequencingSamplesTable)
            .join(SequencingUploadsTable)
            .filter(SequencingUploadsTable.id == sequencingUploadId)
            .all()
        )

        # Define the as_dict method within this function
        def as_dict(instance):
            """Convert SQLAlchemy model instance to a dictionary."""
            return {
                column.name: getattr(instance, column.name)
                for column in instance.__table__.columns
            }

        # Convert each sample instance to a dictionary
        sequencer_ids_list = [
            as_dict(sequencer_id) for sequencer_id in sequencer_ids
        ]

        # Close the session
        session.close()

        return sequencer_ids_list

    @classmethod
    def mark_upload_confirmed_as_true(cls, process_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = (
            session.query(SequencingUploadsTable)
            .filter_by(id=process_id)
            .first()
        )

        if upload:
            upload.metadata_upload_confirmed = True
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def validate_samples(cls, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Get the upload instance
        upload = session.query(SequencingUploadsTable).filter_by(id=id).first()
        if not upload:
            session.close()
            return False  # Upload not found

        # Query to get all samples and their sequencer IDs
        samples = (
            session.query(SequencingSamplesTable)
            .options(joinedload(SequencingSamplesTable.sequencer_ids))
            .filter_by(sequencingUploadId=id)
            .all()
        )

        session.close()

        upload = cls.get(id)

        nr_files_per_sequence = cls.determine_nr_files_per_sequence(
            upload["Sequencing_platform"]
        )
        regions = cls.get_regions(
            upload["region_1_forward_primer"],
            upload["region_1_reverse_primer"],
            upload["region_2_forward_primer"],
            upload["region_2_reverse_primer"],
        )

        for sample in samples:
            sequencer_ids = (
                sample.sequencer_ids
            )  # Assuming `sequencer_ids` is a relationship
            if len(sequencer_ids) != nr_files_per_sequence:
                return False  # Incorrect number of sequencer IDs

            sample_regions = {
                sid.Region for sid in sequencer_ids if sid.Region
            }
            if not sample_regions.issubset(set(regions)):
                return False  # Incorrect regions

        return True

    @classmethod
    def get_uploaded_files(cls, sequencingUploadId):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the SequencingUpload instance
        upload_instance = (
            session.query(SequencingUploadsTable)
            .filter_by(id=sequencingUploadId)
            .first()
        )

        # If no instance is found, return an empty result
        # or handle the case as needed
        if not upload_instance:
            session.close()
            return []

        # Access the 'bucket' and 'uploads_folder' fields
        bucket = upload_instance.project_id
        uploads_folder = upload_instance.uploads_folder

        # Query to get all SequencingFilesUploadedTable entries
        # associated with the given sequencingUploadId
        uploaded_files = (
            session.query(
                SequencingFilesUploadedTable,  # Select the files
                SequencingSamplesTable.id.label(
                    "sample_id"
                ),  # Select the corresponding sample_id
                SequencingSequencerIDsTable.Region,
            )
            .join(
                SequencingSequencerIDsTable,
                SequencingFilesUploadedTable.sequencerId
                == SequencingSequencerIDsTable.id,
            )
            .join(
                SequencingSamplesTable,
                SequencingSequencerIDsTable.sequencingSampleId
                == SequencingSamplesTable.id,
            )
            .filter(
                SequencingSamplesTable.sequencingUploadId == sequencingUploadId
            )
            .all()
        )

        # Define the as_dict method within this function
        def as_dict(instance):
            """Convert SQLAlchemy model instance to a dictionary."""
            return {
                column.name: getattr(instance, column.name)
                for column in instance.__table__.columns
            }

        # Convert each file instance and sample_id to a dictionary
        uploaded_files_list = [
            {
                **as_dict(file),  # File data
                "sample_id": sample_id,  # Include the sample_id
                "region": region,
                "fastqc_report": check_fastqc_report(
                    file.new_name, bucket, region, uploads_folder
                ),  # Include the fastqc_report
            }
            for file, sample_id, region in uploaded_files
        ]

        # Close the session
        session.close()

        return uploaded_files_list

    @classmethod
    def get_by_user_id(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query to get the IDs of uploads for the given user_id
        uploads = (
            session.query(SequencingUploadsTable.id)
            .filter_by(user_id=user_id)
            .all()
        )

        # Extract the upload IDs from the query results
        upload_ids = [upload.id for upload in uploads]

        # Ensure the session is closed after the operation
        session.close()

        return upload_ids if upload_ids else []

    @classmethod
    def delete_upload_and_files(cls, upload_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = (
            session.query(SequencingUploadsTable)
            .filter_by(id=upload_id)
            .first()
        )
        if not upload_db:
            session.close()
            logger.error(f"No upload found with id {upload_id}")
            return

        if upload_db.uploads_folder:
            uploads_directory = Path("uploads", upload_db.uploads_folder)
            extract_directory = Path("processing", upload_db.uploads_folder)

            try:
                shutil.rmtree(uploads_directory)
                logger.info(
                    "Directory '{}' and its contents "
                    "deleted successfully.".format(uploads_directory)
                )
            except Exception as e:
                logger.error(
                    f"Error deleting directory '{uploads_directory}': {e}"
                )

            try:
                shutil.rmtree(extract_directory)
                logger.info(
                    f"Directory '{extract_directory}' and contents deleted."
                )
            except Exception as e:
                logger.error(
                    f"Error deleting directory '{extract_directory}': {e}"
                )

        try:
            session.delete(upload_db)
            session.commit()
            logger.info(
                f"Upload record with id {upload_id} deleted successfully."
            )
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Error deleting upload record: {e}")
        finally:
            session.close()

    @classmethod
    def check_missing_sequencer_ids(cls, process_id):
        """
        Checks if any related sampleID does not have a
        sequencerID for one of its regions.
        Returns a list of sample IDs with missing sequencer IDs.
        """
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Retrieve the SequencingUpload instance
        # to get Sequencing_regions_number
        upload_instance = (
            session.query(SequencingUploadsTable)
            .filter_by(id=process_id)
            .first()
        )

        if not upload_instance:
            session.close()
            raise ValueError(
                f"No SequencingUpload found with ID: {process_id}"
            )

        # Get the number of regions from the SequencingUpload instance
        expected_regions_number = upload_instance.Sequencing_regions_number

        # Query to get all samples related to the given process_id
        samples = (
            session.query(SequencingSamplesTable)
            .join(SequencingUploadsTable)
            .filter(SequencingUploadsTable.id == process_id)
            .all()
        )

        # List to store samples with missing sequencer IDs
        samples_with_missing_ids = []

        # Iterate over each sample and check the number of sequencer IDs
        for sample in samples:
            # Query to get all sequencer IDs associated with this sample
            sequencer_ids = (
                session.query(SequencingSequencerIDsTable)
                .filter(
                    SequencingSequencerIDsTable.sequencingSampleId == sample.id
                )
                .all()
            )

            # Check if the number of sequencer IDs matches
            # the expected number of regions
            if len(sequencer_ids) < expected_regions_number:
                # If not, add the sample ID to the list
                samples_with_missing_ids.append(sample.id)

        # Close the session
        session.close()

        # Return the list of sample IDs with missing sequencer IDs
        return samples_with_missing_ids

    @classmethod
    def get_samples_with_sequencers_and_files(self, sequencingUploadId):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the SequencingUpload instance
        upload_instance = (
            session.query(SequencingUploadsTable)
            .filter_by(id=sequencingUploadId)
            .first()
        )

        # If no instance is found, return an empty result or handle
        # the case as needed
        if not upload_instance:
            session.close()
            return []

        # Access the 'project' field
        bucket = upload_instance.project_id
        uploads_folder = upload_instance.uploads_folder

        # Fetch related samples
        samples = (
            session.query(SequencingSamplesTable)
            .filter_by(sequencingUploadId=sequencingUploadId)
            .all()
        )

        # Fetch related sequencer IDs
        sequencer_ids = (
            session.query(SequencingSequencerIDsTable)
            .join(SequencingSamplesTable)
            .filter(
                SequencingSamplesTable.sequencingUploadId == sequencingUploadId
            )
            .all()
        )

        # Fetch related uploaded files
        uploaded_files = (
            session.query(
                SequencingFilesUploadedTable,  # Select the files
                SequencingSamplesTable.id.label(
                    "sample_id"
                ),  # Select the corresponding sample_id
                SequencingSequencerIDsTable.Region,
            )
            .join(
                SequencingSequencerIDsTable,
                SequencingFilesUploadedTable.sequencerId
                == SequencingSequencerIDsTable.id,
            )
            .join(
                SequencingSamplesTable,
                SequencingSequencerIDsTable.sequencingSampleId
                == SequencingSamplesTable.id,
            )
            .filter(
                SequencingSamplesTable.sequencingUploadId == sequencingUploadId
            )
            .all()
        )

        # Convert the fetched data to dictionaries
        def as_dict(instance):
            """Convert SQLAlchemy model instance to a dictionary."""
            return {
                column.name: getattr(instance, column.name)
                for column in instance.__table__.columns
            }

        samples_dict = {sample.id: as_dict(sample) for sample in samples}
        sequencer_ids_dict = {}
        for sequencer in sequencer_ids:
            sample_id = sequencer.sequencingSampleId
            if sample_id not in sequencer_ids_dict:
                sequencer_ids_dict[sample_id] = []
            sequencer_ids_dict[sample_id].append(as_dict(sequencer))

        uploaded_files_dict = {}
        for file, sample_id, region in uploaded_files:
            # Check if the FastQC report exists
            fastqc_report = check_fastqc_report(
                file.new_name, bucket, region, uploads_folder
            )
            if not fastqc_report:
                processed_folder = f"seq_processed/{uploads_folder}"
                init_create_fastqc_report(
                    file.new_name, processed_folder, bucket, region
                )

            sequencer_id = file.sequencerId
            if sample_id not in uploaded_files_dict:
                uploaded_files_dict[sample_id] = {}
            if sequencer_id not in uploaded_files_dict[sample_id]:
                uploaded_files_dict[sample_id][sequencer_id] = []

            # Convert the file to a dictionary and add the fastqc_report field
            file_dict = as_dict(file)
            file_dict["fastqc_report"] = fastqc_report

            # Append the file dictionary with the fastqc_report to the list
            uploaded_files_dict[sample_id][sequencer_id].append(file_dict)

        # Combine the data into a structured list
        result = []
        for sample_id, sample_data in samples_dict.items():
            sample_data["sequencer_ids"] = sequencer_ids_dict.get(
                sample_id, []
            )
            for sequencer in sample_data["sequencer_ids"]:
                sequencer_id = sequencer["id"]
                sequencer["uploaded_files"] = uploaded_files_dict.get(
                    sample_id, {}
                ).get(sequencer_id, [])
            result.append(sample_data)

        # Close the session
        session.close()
        return result

    @classmethod
    def update_field(cls, id, fieldname, value):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the existing record
        upload_db = (
            session.query(SequencingUploadsTable).filter_by(id=id).first()
        )

        if not upload_db:
            session.close()
            return None

        # Update the specified field
        setattr(upload_db, fieldname, value)

        # Commit the changes
        session.commit()
        session.close()

        return True

    @classmethod
    def generate_mapping_files_for_process(self, process_id):

        samples_data_complete = self.get_samples_with_sequencers_and_files(
            process_id
        )
        process_data = self.get(process_id)
        uploads_folder = process_data["uploads_folder"]

        country = process_data["Country"]
        # Dictionary to hold data organized by region
        region_data = defaultdict(list)

        # lets get the primer sequences for regions
        region_1_sequences = get_sequences_based_on_primers(
            process_data["region_1_forward_primer"],
            process_data["region_1_reverse_primer"],
        )
        region_2_sequences = get_sequences_based_on_primers(
            process_data["region_2_forward_primer"],
            process_data["region_2_reverse_primer"],
        )

        region_dict = {}
        # Add region 1 data if available
        if region_1_sequences:
            region_dict[region_1_sequences["Region"]] = {
                "Forward Primer": region_1_sequences["Forward Primer"],
                "Reverse Primer": region_1_sequences["Reverse Primer"],
            }

        # Add region 2 data if available
        if region_2_sequences:
            region_dict[region_2_sequences["Region"]] = {
                "Forward Primer": region_2_sequences["Forward Primer"],
                "Reverse Primer": region_2_sequences["Reverse Primer"],
            }

        # Dictionary to accumulate files and other information for each sample
        sample_info = {}

        # Process each sample data
        for sample_data in samples_data_complete:
            sample_id = sample_data["SampleID"]
            site_name = sample_data["Site_name"]
            latitude = sample_data["Latitude"]
            longitude = sample_data["Longitude"]
            vegetation = sample_data["Vegetation"]
            land_use = sample_data["Land_use"]
            ecosystem = sample_data["Ecosystem"]
            sample_or_control = sample_data["Sample_or_Control"]
            sequencing_run = sample_data["SequencingRun"]

            # Initialize sample_info dictionary if not already
            if sample_id not in sample_info:
                sample_info[sample_id] = {
                    "site_name": site_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "vegetation": vegetation,
                    "land_use": land_use,
                    "ecosystem": ecosystem,
                    "sample_or_control": sample_or_control,
                    "sequencing_run": sequencing_run,
                    "files": defaultdict(list),  # Accumulate files by region
                }

            # Check if there are sequencers and uploaded files
            if "sequencer_ids" in sample_data:
                for sequencer in sample_data["sequencer_ids"]:
                    region = sequencer["Region"]
                    if "uploaded_files" in sequencer:
                        for file_data in sequencer["uploaded_files"]:
                            fastq_file = file_data["new_name"]
                            # Accumulate files for this sample and region
                            sample_info[sample_id]["files"][region].append(
                                fastq_file
                            )

        # Create directory for output files if it doesn't exist
        output_dir = "output_files"
        output_dir = f"seq_processed/{uploads_folder}/" f"mapping_files/"
        os.makedirs(output_dir, exist_ok=True)

        # Write files for each region
        for sample_id, info in sample_info.items():
            site_name = info["site_name"]
            latitude = info["latitude"]
            longitude = info["longitude"]
            vegetation = info["vegetation"]
            land_use = info["land_use"]
            ecosystem = info["ecosystem"]
            sample_or_control = info["sample_or_control"]
            sequencing_run = info["sequencing_run"]

            for region, files in info["files"].items():
                # Sort filenames alphabetically and join with commas
                sorted_files = sorted(files)
                fastq_files_combined = ",".join(sorted_files)

                forward_primer = region_dict[region]["Forward Primer"]
                reverse_primer = region_dict[region]["Reverse Primer"]
                # Add row to region data
                region_data[region].append(
                    [
                        sample_id,
                        fastq_files_combined,
                        forward_primer,
                        reverse_primer,
                        site_name,
                        latitude,
                        longitude,
                        country,
                        vegetation,
                        land_use,
                        ecosystem,
                        sample_or_control,
                        sequencing_run,
                    ]
                )

        # Write each region's data to a TSV file
        for region, rows in region_data.items():
            output_file_path = os.path.join(
                output_dir, f"{region}_Mapping.txt"
            )
            with open(output_file_path, "w", newline="") as file:
                writer = csv.writer(file, delimiter="\t")
                writer.writerow(
                    [
                        "#SampleID",
                        "fastqFile",
                        "ForwardPrimer",
                        "ReversePrimer",
                        "Site_name",
                        "Latitude",
                        "Longitude",
                        "Country",
                        "Vegetation",
                        "Land_use",
                        "Ecosystem",
                        "Sample_or_Control",
                        "SequencingRun",
                    ]
                )
                writer.writerows(rows)

        return []

    @classmethod
    def check_mapping_files_exist(self, process_id):
        process_data = self.get(process_id)

        # Extract uploads folder and project id from process data
        uploads_folder = process_data["uploads_folder"]

        # Construct the path to the mappings folder
        mappings_folder = os.path.join(
            "seq_processed", uploads_folder, "mapping_files"
        )

        # Check if regions are specified
        if process_data["regions"]:
            # Iterate through each region
            for region in process_data["regions"]:

                # Construct the path to the potential mappings file
                mapping_file = os.path.join(
                    mappings_folder, f"{region}_Mapping.txt"
                )

                # Check if the mapping file exists
                if not os.path.isfile(mapping_file):
                    # If any mapping file does not exist, return
                    # False immediately
                    return False

            # If all reports exist, return True
            return True

        else:
            # If there are no regions specified, we can assume
            # mappings do not exist
            return False
