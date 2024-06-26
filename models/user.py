from flask_login import UserMixin

from helpers.dbm import connect_db, get_session
from models.db_model import UserTable, UploadTable, BucketTable
from sqlalchemy import func
import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class User(UserMixin):
    def __init__(
        self, id_, name, email, profile_pic, admin, approved, buckets=None
    ):
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.admin = admin
        self.approved = approved
        self.buckets = buckets or []

    @classmethod
    def get(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()
        if not user_db:
            return None

        user_buckets = user_db.buckets
        buckets = [bucket.id for bucket in user_buckets]
        session.close()

        user = User(
            id_=user_db.id,
            name=user_db.name,
            email=user_db.email,
            profile_pic=user_db.profile_pic,
            admin=user_db.admin,
            approved=user_db.approved,
            buckets=buckets,
        )

        return user

    @classmethod
    def create(
        cls, id_, name, email, profile_pic, admin=False, approved=False
    ):
        db_engine = connect_db()
        session = get_session(db_engine)

        new_user = UserTable(
            id=id_,
            name=name,
            email=email,
            profile_pic=profile_pic,
            admin=admin,
            approved=approved,
        )

        session.add(new_user)
        session.commit()

        session.close()

        return id_

    @classmethod
    def get_all(cls):
        db_engine = connect_db()
        session = get_session(db_engine)

        all_users_db = (
            session.query(
                UserTable,
                func.count(UploadTable.id),
                func.count(func.nullif(UploadTable.reviewed_by_admin, False)),
                func.count(func.nullif(UploadTable.reviewed_by_admin, True)),
            )
            .outerjoin(UploadTable)
            .group_by(UserTable.id)
            .all()
        )

        if not all_users_db:
            session.close()
            return []

        all_users = []
        for (
            user_db,
            uploads_count,
            reviewed_true_count,
            reviewed_false_count,
        ) in all_users_db:
            user_buckets = [bucket.id for bucket in user_db.buckets]
            user_info = {
                "user": User(
                    id_=user_db.id,
                    name=user_db.name,
                    email=user_db.email,
                    profile_pic=user_db.profile_pic,
                    admin=user_db.admin,
                    approved=user_db.approved,
                    buckets=user_buckets,
                ),
                "uploads_count": uploads_count if uploads_count else 0,
                "reviewed_by_admin_count": (
                    reviewed_true_count if reviewed_true_count else 0
                ),
            }
            all_users.append(user_info)

        session.close()
        return all_users

    @classmethod
    def update_admin_status(cls, user_id, new_admin_status):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.admin = new_admin_status
            session.commit()

        session.close()

    @classmethod
    def add_user_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            bucket = (
                session.query(BucketTable).filter_by(id=bucket_name).first()
            )
            if bucket:
                user.buckets.append(bucket)
                session.commit()
            else:
                session.close()
                raise ValueError(f"Bucket '{bucket_name}' not found")
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def delete_user_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            bucket = (
                session.query(BucketTable).filter_by(id=bucket_name).first()
            )
            if bucket:
                user.buckets.remove(bucket)
                session.commit()
            else:
                session.close()
                raise ValueError(f"Bucket '{bucket_name}' not found")
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def update_approved_status(cls, user_id, new_approved_status):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.approved = new_approved_status
            session.commit()

        session.close()

    @classmethod
    def has_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            # Explicitly load the buckets relationship before closing the
            # session
            user_buckets = user.buckets  # This will trigger a lazy load
            session.close()
            return bucket_name in [bucket.id for bucket in user_buckets]
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def delete(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)
        to_return = {"status": 0, "message": "Not run"}
        # Check if the user has uploads
        uploads_count = (
            session.query(func.count(UploadTable.id))
            .filter_by(user_id=user_id)
            .scalar()
        )

        if uploads_count == 0:
            user_db = session.query(UserTable).filter_by(id=user_id).first()
            if user_db:
                # Delete user's bucket accesses
                for bucket in user_db.buckets:
                    user_db.buckets.remove(bucket)

                # Delete the user
                session.delete(user_db)
                session.commit()
                to_return = {"status": 1, "message": "Success"}
            else:
                to_return = {
                    "status": 0,
                    "message": "Not deleted. User doesnt exist",
                }
        else:
            to_return = {"status": 0, "message": "Not deleted. Uploads exist"}
        session.close()
        return to_return
