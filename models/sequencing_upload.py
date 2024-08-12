import datetime
import random
import string
import logging
import os
import json
import shutil
from helpers.dbm import connect_db, get_session
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
            filtered_dict["Primer_set_1"], filtered_dict["Primer_set_2"]
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
                filtered_dict["Primer_set_1"], filtered_dict["Primer_set_2"]
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
    def get_regions(cls, primer_set_1=None, primer_set_2=None):
        current_dir = os.path.dirname(__file__)
        base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
        regions_file_path = os.path.join(
            base_dir, "metadataconfig", "primer_set_regions.json"
        )

        # Load the JSON file
        with open(regions_file_path, "r") as f:
            primer_set_region = json.load(f)

        # Check if process_data exists
        if primer_set_1 is None and primer_set_2 is None:
            # If process_data does not exist, return all available regions
            data = list(primer_set_region.values())
        else:
            data = []
            if primer_set_1 in primer_set_region:
                data.append(primer_set_region[primer_set_1])
            if primer_set_2 in primer_set_region:
                data.append(primer_set_region[primer_set_2])

        data = list(set(data))
        return data

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
            datadict["Primer_set_1"] = "ITS3/ITS4"
            datadict["Primer_set_2"] = "WANDA/AML2"
            datadict["Sequencing_platform"] = "Element Biosciences AVITI"
            datadict["Sequencing_facility"] = "Scripps Research"

        if datadict["Primer_set_2"] == "0":
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
            upload["Primer_set_1"], upload["Primer_set_2"]
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

        # Query to get all SequencingFilesUploadedTable entries
        # associated with the given sequencingUploadId
        uploaded_files = (
            session.query(SequencingFilesUploadedTable)
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

        # Convert each file instance to a dictionary
        uploaded_files_list = [as_dict(file) for file in uploaded_files]

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
