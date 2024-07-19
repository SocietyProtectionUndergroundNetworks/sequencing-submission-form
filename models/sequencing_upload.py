import logging
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingUploadsTable,
    SequencingSamplesTable,
    SequencingSequencerIDsTable,
)
from pathlib import Path
from flask_login import current_user

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingUpload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.path = Path("uploads", self.uploads_folder)

    @classmethod
    def get(self, id):
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

        # Create an instance of YourClass using the dictionary
        upload = SequencingUploadsTable(**filtered_dict)

        return upload

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
