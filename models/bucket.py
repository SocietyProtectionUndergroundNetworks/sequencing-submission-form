import logging
from models.db_model import BucketTable
from helpers.dbm import session_scope

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class Bucket:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            bucket_db = session.query(BucketTable).filter_by(id=id).first()

            if not bucket_db:
                return None

            # Assuming upload_db is an instance of some SQLAlchemy model
            bucket_db_dict = bucket_db.__dict__

            # Remove keys starting with '_'
            filtered_dict = {
                key: value
                for key, value in bucket_db_dict.items()
                if not key.startswith("_")
            }

            # Create an instance of YourClass using the dictionary
            bucket = Bucket(**filtered_dict)

            return bucket

    @classmethod
    def create(cls, id):
        with session_scope() as session:
            existing_bucket = (
                session.query(BucketTable).filter_by(id=id).first()
            )

            if existing_bucket:
                return existing_bucket.id

            new_bucket = BucketTable(id=id)
            session.add(new_bucket)
            session.commit()
            session.refresh(new_bucket)

            return new_bucket.id

    @classmethod
    def get_all(cls, order_by="name"):
        with session_scope() as session:
            # Dynamically set the ordering column
            order_column = (
                BucketTable.cohort if order_by == "cohort" else BucketTable.id
            )

            # Query with dynamic ordering
            all_buckets_db = (
                session.query(BucketTable).order_by(order_column).all()
            )

            # Transform the results into a list of dictionaries
            return [
                {"id": bucket_db.id, "cohort": bucket_db.cohort}
                for bucket_db in all_buckets_db
            ]

    @classmethod
    def update_progress(cls, id, progress):
        with session_scope() as session:
            bucket = session.query(BucketTable).filter_by(id=id).first()

            if not bucket:
                return False

            bucket.archive_file_creation_progress = progress
            session.commit()

            return True

    @classmethod
    def update_archive_filename(cls, id, filename):
        with session_scope() as session:
            bucket = session.query(BucketTable).filter_by(id=id).first()

            if bucket:
                bucket.archive_file = filename
                session.commit()
                return True
            else:
                return False

    @classmethod
    def update_cohort(cls, id, cohort):
        with session_scope() as session:
            bucket = session.query(BucketTable).filter_by(id=id).first()

            if bucket:
                bucket.cohort = cohort
                session.commit()
                return True
            else:
                return False
