import logging
from helpers.dbm import session_scope
from models.db_model import SequencingAnalysisTypesTable

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingAnalysisType:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:
            item_db = (
                session.query(SequencingAnalysisTypesTable)
                .filter_by(id=id)
                .first()
            )

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

    @classmethod
    def get_all_by_region(cls, region):
        with session_scope() as session:
            # Query for all items with the specified region
            items = (
                session.query(SequencingAnalysisTypesTable)
                .filter_by(region=region)
                .all()
            )

            # Format results as a list of dictionaries with specific fields
            results = [
                {
                    "id": item.id,
                    "name": item.name,
                    "parameters": item.parameters,
                }
                for item in items
            ]

            return results

    @classmethod
    def get_all(cls):
        with session_scope() as session:
            # Query for all items with the specified region
            items = session.query(SequencingAnalysisTypesTable).all()

            # Format results as a list of dictionaries with specific fields
            results = [
                {
                    "id": item.id,
                    "name": item.name,
                    "parameters": item.parameters,
                }
                for item in items
            ]

            return results
