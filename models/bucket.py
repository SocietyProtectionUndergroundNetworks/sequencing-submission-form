import logging
from models.db_model import BucketTable
from helpers.dbm import connect_db, get_session
from datetime import datetime
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
        bucket = Bucket(**filtered_dict)

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


    @classmethod
    def get_all(cls):
        db_engine = connect_db()
        session = get_session(db_engine)

        all_buckets_db = session.query(BucketTable).all()

        buckets = []
        for bucket_db in all_buckets_db:
            bucket = Bucket(id_=bucket_db.id)
            buckets.append(bucket)

        session.close()
        return buckets
        
    @classmethod
    def update_progress(cls, id, progress):
        db_engine = connect_db()
        session = get_session(db_engine)
        bucket = session.query(BucketTable).filter_by(id=id).first()

        if bucket:
            bucket.archive_file_creation_progress = progress

            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False       
            
    @classmethod
    def update_archive_filename(cls, id, filename):
        db_engine = connect_db()
        session = get_session(db_engine)
        bucket = session.query(BucketTable).filter_by(id=id).first()

        if bucket:
            bucket.archive_file = filename

            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False     