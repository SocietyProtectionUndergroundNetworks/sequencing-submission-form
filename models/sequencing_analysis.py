import logging
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingAnalysisTable,
    SequencingAnalysisTypesTable,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingAnalysis:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        item_db = (
            session.query(SequencingAnalysisTable).filter_by(id=id).first()
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
        upload = SequencingAnalysisTable(**filtered_dict)

        return upload

    @classmethod
    def create(cls, sequencingUploadId, sequencingAnalysisTypeId):
        # Try to get an existing record using the get_by_upload_and_type method
        existing_item = cls.get_by_upload_and_type(
            sequencingUploadId, sequencingAnalysisTypeId
        )

        if existing_item:
            # If it exists, return the ID of the existing record
            return existing_item

        # If it doesn't exist, create a new record
        db_engine = connect_db()
        session = get_session(db_engine)

        new_item = SequencingAnalysisTable(
            sequencingUploadId=sequencingUploadId,
            sequencingAnalysisTypeId=sequencingAnalysisTypeId,
        )

        session.add(new_item)
        session.commit()

        # Get the ID of the newly created record
        new_id = new_item.id

        session.close()

        return new_id

    @classmethod
    def get_by_upload_and_type(
        cls, sequencingUploadId, sequencingAnalysisTypeId
    ):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query the database for the item matching both sequencingUploadId
        # and sequencingAnalysisTypeId
        item_db = (
            session.query(SequencingAnalysisTable)
            .filter_by(
                sequencingUploadId=sequencingUploadId,
                sequencingAnalysisTypeId=sequencingAnalysisTypeId,
            )
            .first()
        )

        session.close()

        if not item_db:
            return None

        return item_db.id

    @classmethod
    def get_by_upload(cls, sequencingUploadId):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query the database for all items matching the sequencingUploadId,
        # joining with the SequencingAnalysisTypesTable to
        # include analysisTypeName
        items = (
            session.query(
                SequencingAnalysisTable,
                SequencingAnalysisTypesTable.name.label("analysisTypeName"),
                SequencingAnalysisTypesTable.id.label("analysisTypeId"),
                SequencingAnalysisTypesTable.region,
            )
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTable.sequencingAnalysisTypeId
                == SequencingAnalysisTypesTable.id,
            )
            .filter(
                SequencingAnalysisTable.sequencingUploadId
                == sequencingUploadId
            )
            .all()
        )

        session.close()
        # Format the results as a list of dictionaries with desired fields
        results = [
            {
                "id": item.SequencingAnalysisTable.id,
                "sequencingUploadId": (
                    item.SequencingAnalysisTable.sequencingUploadId
                ),
                "analysisTypeId": item.analysisTypeId,
                "analysisTypeName": item.analysisTypeName,
                "region": item.region,
                "lotus2_status": item.SequencingAnalysisTable.lotus2_status,
                "rscripts_status": (
                    item.SequencingAnalysisTable.rscripts_status
                ),
            }
            for item in items
        ]

        return results

    @classmethod
    def update_field(cls, id, fieldname, value):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the existing record
        upload_db = (
            session.query(SequencingAnalysisTable).filter_by(id=id).first()
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
