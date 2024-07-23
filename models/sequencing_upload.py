import logging
import os
import json
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingUploadsTable,
    SequencingSamplesTable,
    SequencingSequencerIDsTable,
)
from pathlib import Path
from flask_login import current_user
from sqlalchemy.orm import joinedload

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
        samples = session.query(SequencingSamplesTable).options(
            joinedload(SequencingSamplesTable.sequencer_ids)
        ).filter_by(sequencingUploadId=id).all()

        session.close()
        
        upload = cls.get(id)
        
        nr_files_per_sequence = cls.determine_nr_files_per_sequence(
            upload["Sequencing_platform"]
        )
        regions = cls.get_regions(
            upload["Primer_set_1"],upload["Primer_set_2"]
        )
        
        for sample in samples:
            sequencer_ids = sample.sequencer_ids  # Assuming `sequencer_ids` is a relationship
            if len(sequencer_ids) != nr_files_per_sequence:
                return False  # Incorrect number of sequencer IDs

            sample_regions = {sid.Region for sid in sequencer_ids if sid.Region}
            if not sample_regions.issubset(set(regions)):
                return False  # Incorrect regions

        return True