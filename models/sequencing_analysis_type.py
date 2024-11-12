import logging
from helpers.dbm import connect_db, get_session
from models.db_model import SequencingAnalysisTypesTable

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingAnalysisType:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        item_db = (
            session.query(SequencingAnalysisTypesTable)
            .filter_by(id=id)
            .first()
        )

        session.close()

        if not item_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        item_db_dict = item_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in item_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of YourClass using the dictionary
        upload = SequencingAnalysisTypesTable(**filtered_dict)

        return upload
