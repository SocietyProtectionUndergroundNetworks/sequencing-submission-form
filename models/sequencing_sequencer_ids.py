import logging
from helpers.dbm import connect_db, get_session
from models.db_model import SequencingSequencerIDsTable
from sqlalchemy import and_

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingSequencerId:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        sequencer_id_db = (
            session.query(SequencingSequencerIDsTable).filter_by(id=id).first()
        )

        session.close()

        if not sequencer_id_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        sequencer_id_db_dict = sequencer_id_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in sequencer_id_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of YourClass using the dictionary
        sequencer_id = SequencingSequencerId(**filtered_dict)

        return sequencer_id

    @classmethod
    def create(cls, sample_id, sequencer_id, region):
        db_engine = connect_db()
        session = get_session(db_engine)

        existing_record = (
            session.query(SequencingSequencerIDsTable)
            .filter(
                and_(
                    SequencingSequencerIDsTable.sequencingSampleId
                    == sample_id,
                    SequencingSequencerIDsTable.SequencerID == sequencer_id,
                    SequencingSequencerIDsTable.Region == region,
                )
            )
            .first()
        )

        if existing_record:
            # If record exists, return its id
            return existing_record.id, "existing"
        else:
            # If record does not exist, create a new one
            new_record = SequencingSequencerIDsTable(
                sequencingSampleId=sample_id,
                SequencerID=sequencer_id,
                Region=region,
            )
            session.add(new_record)
            session.commit()
            # Return the id of the newly created record
            return new_record.id, "new"
