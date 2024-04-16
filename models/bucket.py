import logging
from models.db_model import BucketTable
from helpers.dbm import connect_db, get_session
# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

class Bucket():
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        bucket_db = session.query(BucketTable).filter_by(id=id).first()

        session.close()

        if not bucket_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        bucket_db_dict = bucket_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {key: value for key, value in bucket_db_dict.items() if not key.startswith('_')}

        # Create an instance of YourClass using the dictionary
        bucket = Upload(**filtered_dict)

        return bucket

    @classmethod
    def create(cls, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        existing_bucket = session.query(BucketTable).filter_by(id=id).first()

        if existing_bucket:
            session.close()
            return existing_bucket.id

        new_bucket = BucketTable(id=id)

        session.add(new_bucket)
        session.commit()

        # Refresh the object to get the updated ID
        session.refresh(new_bucket)

        new_bucket_id = new_bucket.id

        session.close()

        return new_bucket_id
