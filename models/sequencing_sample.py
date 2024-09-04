import logging
from helpers.dbm import connect_db, get_session
from models.db_model import SequencingSamplesTable

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingSample:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = (
            session.query(SequencingSamplesTable).filter_by(id=id).first()
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
        upload = SequencingSamplesTable(**filtered_dict)

        return upload

    @classmethod
    def create(cls, sequencingUploadId, datadict):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Convert 'yes'/'no' to boolean for specific field
        datadict = {
            k: (v.lower() == "yes") if k == "using_scripps" else v
            for k, v in datadict.items()
        }

        # Get valid columns from the table's model class
        valid_keys = {c.name for c in SequencingSamplesTable.__table__.columns}

        # Filter out valid keys to create the filtered data dictionary
        filtered_datadict = {
            key: value for key, value in datadict.items() if key in valid_keys
        }

        # Identify the extra columns
        extra_columns = {
            key: value
            for key, value in datadict.items()
            if key not in valid_keys
        }

        # Include sequencingUploadId in the filters
        filters = [
            getattr(SequencingSamplesTable, key) == value
            for key, value in filtered_datadict.items()
        ]
        filters.append(
            SequencingSamplesTable.sequencingUploadId == sequencingUploadId
        )

        # Query to check if identical record exists
        existing_record = (
            session.query(SequencingSamplesTable).filter(*filters).first()
        )

        if existing_record:
            session.close()
            return existing_record.id

        # If no existing record is found, create a new one
        new_sample = SequencingSamplesTable(
            sequencingUploadId=sequencingUploadId,
        )

        for key, value in filtered_datadict.items():
            if hasattr(new_sample, key):
                setattr(new_sample, key, value)

        # Add extra columns to the extracolumns_json field as JSON
        if extra_columns:
            new_sample.extracolumns_json = extra_columns

        session.add(new_sample)
        session.commit()

        session.refresh(new_sample)

        new_sample_id = new_sample.id

        session.close()

        return new_sample_id
